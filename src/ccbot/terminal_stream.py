"""Terminal streaming — periodic pane capture with diff-based delivery.

Captures tmux pane content at regular intervals and delivers only
changed content to subscribed WebSocket clients. Each window has
its own streaming task, started on first subscription and stopped
when no subscribers remain.

Key class: TerminalStreamer — manages per-window capture loops.
"""

import asyncio
import logging
from typing import Callable, Awaitable

from .tmux_manager import tmux_manager

logger = logging.getLogger(__name__)

# Capture interval in seconds (200ms balances responsiveness vs CPU)
CAPTURE_INTERVAL = 0.2
MAX_SUBSCRIBERS_PER_WINDOW = 10


class TerminalStreamer:
    """Manages per-window terminal capture tasks."""

    def __init__(
        self,
        on_data: Callable[[str, str], Awaitable[None]],
    ) -> None:
        """Initialize streamer.

        Args:
            on_data: async callback(window_id, ansi_text) called on content change.
        """
        self._on_data = on_data
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._subscribers: dict[str, int] = {}  # window_id -> count

    def subscribe(self, window_id: str) -> bool:
        """Add a subscriber for a window's terminal stream.

        Returns False if max subscribers reached.
        """
        count = self._subscribers.get(window_id, 0)
        if count >= MAX_SUBSCRIBERS_PER_WINDOW:
            return False
        self._subscribers[window_id] = count + 1
        if window_id not in self._tasks or self._tasks[window_id].done():
            self._tasks[window_id] = asyncio.create_task(
                self._capture_loop(window_id)
            )
            logger.debug("Terminal stream started for %s", window_id)
        return True

    def unsubscribe(self, window_id: str) -> None:
        """Remove a subscriber. Stream stops when count reaches zero."""
        count = self._subscribers.get(window_id, 0) - 1
        if count <= 0:
            self._subscribers.pop(window_id, None)
            task = self._tasks.pop(window_id, None)
            if task and not task.done():
                task.cancel()
                logger.debug("Terminal stream stopped for %s", window_id)
        else:
            self._subscribers[window_id] = count

    def unsubscribe_all(self, window_id: str) -> None:
        """Remove all subscribers for a window."""
        self._subscribers.pop(window_id, None)
        task = self._tasks.pop(window_id, None)
        if task and not task.done():
            task.cancel()

    async def stop(self) -> None:
        """Cancel all streaming tasks."""
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        self._subscribers.clear()

    async def _capture_loop(self, window_id: str) -> None:
        """Continuously capture pane and emit on change."""
        last_content = ""
        try:
            while window_id in self._subscribers:
                try:
                    content = await tmux_manager.capture_pane(
                        window_id, with_ansi=True
                    )
                    if content and content != last_content:
                        last_content = content
                        await self._on_data(window_id, content)
                except Exception:
                    pass

                await asyncio.sleep(CAPTURE_INTERVAL)
        except asyncio.CancelledError:
            pass
