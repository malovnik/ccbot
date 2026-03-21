"""Auto-approve watcher — polls tmux panes for ALL permission prompts.

Watches tmux panes for Claude Code permission prompts and automatically
approves them. Covers all prompt types:
  - .claude/ self-edit prompts (not covered by --dangerously-skip-permissions)
  - Bash command approval
  - File create/edit/delete/overwrite permission
  - General "Do you want to proceed?" prompts

Per-window control: start/stop watcher per tmux window ID.
Patterns are checked in order — first match wins.
"""

import asyncio
import logging
import re
import time

from .tmux_manager import tmux_manager

logger = logging.getLogger(__name__)

# Each pattern: (regex, keys_to_send)
# keys_to_send: list of (key, enter, literal) tuples
# Patterns checked in order — first match wins.
#
# Strategy for multi-choice menus:
#   - "❯ 1. Yes" → Enter (already on Yes)
#   - "allow all edits during this session" → Down to select it, then Enter
#   - "Do you want to overwrite" with 3 choices → Down to "allow all", Enter
#   - "Do you want to proceed?" with 2 choices → Enter (cursor on Yes)
#   - "Bash command" approval → Enter (cursor on Yes)
#   - .claude/ self-edit → Down to Yes, Enter

_ENTER: list[tuple[str, bool, bool]] = [("Enter", False, False)]
_DOWN_ENTER: list[tuple[str, bool, bool]] = [
    ("Down", False, False),
    ("Enter", False, False),
]
_Y_ENTER: list[tuple[str, bool, bool]] = [("y", True, True)]

_DEFAULT_PATTERNS: list[tuple[re.Pattern[str], list[tuple[str, bool, bool]]]] = [
    # --- "Allow all" shortcuts (check BEFORE generic prompts) ---
    # File overwrite with "allow all edits" option — pick option 2
    (re.compile(r"allow all edits during this session"), _DOWN_ENTER),
    # .claude/ self-edit (v2.1.80+) — "allow Claude to edit its own settings"
    (re.compile(r"allow Claude to edit its own settings"), _DOWN_ENTER),
    # Older .claude/ prompt
    (re.compile(r"authorize Claude to modify its config files"), _Y_ENTER),
    # --- Generic permission prompts (cursor already on Yes) ---
    # Numbered menu: ❯ 1. Yes — just Enter
    (re.compile(r"❯\s*1\.\s*Yes"), _ENTER),
    # "Do you want to proceed?" / "Do you want to overwrite X?" /
    # "Do you want to make this edit" / "Do you want to create" /
    # "Do you want to delete" — all start with "Do you want to"
    (re.compile(r"Do you want to"), _ENTER),
    # Bash command approval — "Bash command" header with "Esc to cancel"
    (re.compile(r"This command requires approval"), _ENTER),
    # "Contains backslash-escaped whitespace" warning with proceed prompt
    (re.compile(r"Contains backslash-escaped whitespace"), _ENTER),
]


class AutoApproveWatcher:
    """Async watcher that auto-approves permission prompts per window."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._patterns = list(_DEFAULT_PATTERNS)

    def start(self, window_id: str) -> bool:
        """Start watching a window. Returns False if already watching."""
        if window_id in self._tasks and not self._tasks[window_id].done():
            return False
        task = asyncio.create_task(self._watch_loop(window_id))
        self._tasks[window_id] = task
        logger.info("Auto-approve watcher started for window %s", window_id)
        return True

    def stop(self, window_id: str) -> bool:
        """Stop watching a window. Returns False if not watching."""
        task = self._tasks.pop(window_id, None)
        if task and not task.done():
            task.cancel()
            logger.info("Auto-approve watcher stopped for window %s", window_id)
            return True
        return False

    def stop_all(self) -> None:
        """Stop all watchers."""
        for wid in list(self._tasks):
            self.stop(wid)

    def is_active(self, window_id: str) -> bool:
        """Check if watcher is active for a window."""
        task = self._tasks.get(window_id)
        return task is not None and not task.done()

    def active_windows(self) -> list[str]:
        """Return list of window IDs being watched."""
        return [wid for wid, task in self._tasks.items() if not task.done()]

    async def _watch_loop(self, window_id: str) -> None:
        """Poll loop: check pane content for patterns every 1.5 seconds."""
        cooldown_until = 0.0
        try:
            while True:
                await asyncio.sleep(1.5)

                # Skip if in cooldown (prevent double-approve)
                now = time.monotonic()
                if now < cooldown_until:
                    continue

                # Check if window still exists
                w = await tmux_manager.find_window_by_id(window_id)
                if not w:
                    logger.info(
                        "Auto-approve: window %s gone, stopping watcher", window_id
                    )
                    break

                # Capture pane content
                pane_text = await tmux_manager.capture_pane(w.window_id)
                if not pane_text:
                    continue

                # Check patterns (first match wins)
                for pattern, keys in self._patterns:
                    if pattern.search(pane_text):
                        logger.info(
                            "Auto-approve: matched '%s' in window %s",
                            pattern.pattern,
                            window_id,
                        )
                        for key, enter, literal in keys:
                            await tmux_manager.send_keys(
                                w.window_id,
                                key,
                                enter=enter,
                                literal=literal,
                            )
                        # Cooldown: wait before checking again to prevent
                        # double-approving the same prompt
                        cooldown_until = time.monotonic() + 3.0
                        break
        except asyncio.CancelledError:
            return
        finally:
            self._tasks.pop(window_id, None)


# Module-level singleton
auto_approve_watcher = AutoApproveWatcher()
