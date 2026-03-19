"""Tests for terminal streaming subscription management."""

from unittest.mock import AsyncMock, MagicMock, patch

from ccbot.terminal_stream import MAX_SUBSCRIBERS_PER_WINDOW, TerminalStreamer


class TestTerminalStreamer:
    def _make_streamer(self) -> TerminalStreamer:
        return TerminalStreamer(on_data=AsyncMock())

    def test_subscribe_first(self) -> None:
        streamer = self._make_streamer()
        with patch("ccbot.terminal_stream.asyncio.create_task") as mock_task:
            mock_task.return_value = AsyncMock()
            result = streamer.subscribe("@0")
        assert result is True
        assert streamer._subscribers["@0"] == 1

    def test_subscribe_increments_count(self) -> None:
        streamer = self._make_streamer()
        with patch("ccbot.terminal_stream.asyncio.create_task") as mock_task:
            mock_task.return_value = AsyncMock()
            streamer.subscribe("@0")
            streamer.subscribe("@0")
        assert streamer._subscribers["@0"] == 2

    def test_subscribe_max_limit(self) -> None:
        streamer = self._make_streamer()
        streamer._subscribers["@0"] = MAX_SUBSCRIBERS_PER_WINDOW
        result = streamer.subscribe("@0")
        assert result is False

    def test_unsubscribe_decrements(self) -> None:
        streamer = self._make_streamer()
        streamer._subscribers["@0"] = 3
        streamer.unsubscribe("@0")
        assert streamer._subscribers["@0"] == 2

    def test_unsubscribe_to_zero_removes(self) -> None:
        streamer = self._make_streamer()
        streamer._subscribers["@0"] = 1
        mock_task = MagicMock()
        mock_task.done.return_value = False
        streamer._tasks["@0"] = mock_task
        streamer.unsubscribe("@0")
        assert "@0" not in streamer._subscribers
        assert "@0" not in streamer._tasks
        mock_task.cancel.assert_called_once()

    def test_unsubscribe_nonexistent(self) -> None:
        streamer = self._make_streamer()
        streamer.unsubscribe("@99")
        assert "@99" not in streamer._subscribers

    def test_unsubscribe_all(self) -> None:
        streamer = self._make_streamer()
        streamer._subscribers["@0"] = 5
        mock_task = MagicMock()
        mock_task.done.return_value = False
        streamer._tasks["@0"] = mock_task
        streamer.unsubscribe_all("@0")
        assert "@0" not in streamer._subscribers
        assert "@0" not in streamer._tasks
        mock_task.cancel.assert_called_once()

    async def test_stop_cancels_all(self) -> None:
        streamer = self._make_streamer()
        t1 = MagicMock()
        t2 = MagicMock()
        streamer._tasks = {"@0": t1, "@1": t2}
        streamer._subscribers = {"@0": 1, "@1": 2}
        await streamer.stop()
        assert streamer._tasks == {}
        assert streamer._subscribers == {}
        t1.cancel.assert_called_once()
        t2.cancel.assert_called_once()
