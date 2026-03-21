"""Auto-approve watcher — polls tmux panes for permission prompts.

Watches tmux panes for Claude Code's .claude/ self-edit permission prompts
and automatically approves them. --dangerously-skip-permissions covers
regular permission prompts but NOT .claude/ self-edit prompts.

Per-window control: start/stop watcher per tmux window ID.
Default patterns match current Claude Code versions.
"""

import asyncio
import logging
import time

from .tmux_manager import tmux_manager

logger = logging.getLogger(__name__)

# (pattern_text, keys_to_send) — keys_to_send is a list of (key, enter, literal) tuples
_DEFAULT_PATTERNS: list[tuple[str, list[tuple[str, bool, bool]]]] = [
    # Pattern 1: .claude/ permission prompt (v2.1.80+) — select "Yes" and confirm
    (
        "allow Claude to edit its own settings",
        [("Down", False, False), ("Enter", False, False)],
    ),
    # Pattern 2: older "authorize Claude to modify its config files" — type y + Enter
    (
        "authorize Claude to modify its config files",
        [("y", True, True)],
    ),
    # Pattern 3: file create/edit permission menu (v2.1.81+) — select "allow all edits"
    (
        "allow all edits during this session",
        [("Down", False, False), ("Enter", False, False)],
    ),
]


class AutoApproveWatcher:
    """Async watcher that auto-approves .claude/ permission prompts per window."""

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
        """Poll loop: check pane content for patterns every 2 seconds."""
        cooldown_until = 0.0
        try:
            while True:
                await asyncio.sleep(2.0)

                # Skip if in cooldown
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

                # Check patterns
                for pattern_text, keys in self._patterns:
                    if pattern_text in pane_text:
                        logger.info(
                            "Auto-approve: matched '%s' in window %s",
                            pattern_text,
                            window_id,
                        )
                        for key, enter, literal in keys:
                            await tmux_manager.send_keys(
                                w.window_id,
                                key,
                                enter=enter,
                                literal=literal,
                            )
                        cooldown_until = time.monotonic() + 3.0
                        break
        except asyncio.CancelledError:
            return
        finally:
            self._tasks.pop(window_id, None)


# Module-level singleton
auto_approve_watcher = AutoApproveWatcher()
