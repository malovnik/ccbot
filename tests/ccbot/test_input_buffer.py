"""Tests for input buffer batching and cleanup."""

import asyncio

from ccbot.bot import _cancel_input_buffer, _input_buffer, _input_timer


class TestCancelInputBuffer:
    def setup_method(self) -> None:
        _input_buffer.clear()
        for task in _input_timer.values():
            if not task.done():
                task.cancel()
        _input_timer.clear()

    def test_cancel_empty_buffer(self) -> None:
        _cancel_input_buffer(123, 456)
        assert (123, 456) not in _input_buffer
        assert (123, 456) not in _input_timer

    def test_cancel_with_pending_messages(self) -> None:
        key = (123, 456)
        _input_buffer[key] = ["hello", "world"]
        _cancel_input_buffer(123, 456)
        assert key not in _input_buffer

    def test_cancel_with_active_timer(self) -> None:
        key = (123, 456)
        _input_buffer[key] = ["test"]

        async def dummy() -> None:
            await asyncio.sleep(100)

        loop = asyncio.new_event_loop()
        task = loop.create_task(dummy())
        _input_timer[key] = task

        _cancel_input_buffer(123, 456)

        assert key not in _input_buffer
        assert key not in _input_timer
        assert task.cancelling()
        loop.close()

    def test_cancel_does_not_affect_other_users(self) -> None:
        _input_buffer[(111, 222)] = ["msg1"]
        _input_buffer[(333, 444)] = ["msg2"]

        _cancel_input_buffer(111, 222)

        assert (111, 222) not in _input_buffer
        assert (333, 444) in _input_buffer
        assert _input_buffer[(333, 444)] == ["msg2"]
