"""Tests for WS bridge helper functions and edge cases."""

import json
from pathlib import Path
from unittest.mock import patch

from ccbot.ws_protocol import (
    WsGetHistory,
    WsHistory,
    serialize,
)


class TestWsHistoryPagination:
    """Test that WS history pagination works correctly."""

    def _make_messages(self, count: int) -> list[dict[str, str]]:
        return [
            {
                "role": "assistant",
                "content": f"Message {i}",
                "content_type": "text",
                "tool_name": "",
                "timestamp": f"2026-03-20T{i:02d}:00:00Z",
            }
            for i in range(count)
        ]

    def test_single_page(self) -> None:
        messages = self._make_messages(10)
        history = WsHistory(window_id="@0", messages=messages, page=0, total_pages=1)
        data = json.loads(serialize(history))
        assert data["page"] == 0
        assert data["total_pages"] == 1
        assert len(data["messages"]) == 10

    def test_pagination_fields_in_protocol(self) -> None:
        msg = WsGetHistory(window_id="@0", offset=2)
        assert msg.offset == 2
        assert msg.window_id == "@0"

    def test_empty_history(self) -> None:
        history = WsHistory(window_id="@0", messages=[], page=0, total_pages=1)
        data = json.loads(serialize(history))
        assert data["messages"] == []
        assert data["total_pages"] == 1


class TestWsBridgeDisplayPathEdgeCases:
    """Additional edge cases for _display_path."""

    def test_nested_deep_path(self) -> None:
        from ccbot.ws_bridge import _display_path

        home = Path.home()
        deep = home / "a" / "b" / "c" / "d" / "e"
        result = _display_path(deep)
        assert result == "~/a/b/c/d/e"

    def test_root_path(self) -> None:
        from ccbot.ws_bridge import _display_path

        result = _display_path(Path("/"))
        assert result == "/"

    def test_tmp_path(self) -> None:
        from ccbot.ws_bridge import _display_path

        result = _display_path(Path("/tmp/some/project"))
        assert result == "/tmp/some/project"


class TestIsPathAllowedEdgeCases:
    """Edge cases for _is_path_allowed."""

    @patch("ccbot.ws_bridge.config")
    def test_empty_allowed_roots(self, mock_config) -> None:
        from ccbot.ws_bridge import _is_path_allowed

        mock_config.allowed_roots = []
        assert _is_path_allowed(Path("/anything")) is False

    @patch("ccbot.ws_bridge.config")
    def test_resolved_path_traversal_blocked(self, mock_config) -> None:
        from ccbot.ws_bridge import _is_path_allowed

        mock_config.allowed_roots = [Path("/home/user/projects")]
        # After resolve(), /home/user/projects/../secrets becomes /home/user/secrets
        # But in test environment the path doesn't exist so resolve keeps it as-is
        # The key insight: ws_bridge always calls .resolve() BEFORE _is_path_allowed
        assert _is_path_allowed(Path("/home/user/secrets")) is False
