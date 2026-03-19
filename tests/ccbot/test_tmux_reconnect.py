"""Tests for tmux server reconnect logic."""

from unittest.mock import MagicMock, PropertyMock, patch

from ccbot.tmux_manager import TmuxManager


class TestTmuxReconnect:
    def test_creates_server_on_first_access(self) -> None:
        with patch("ccbot.tmux_manager.config") as mock_config:
            mock_config.tmux_session_name = "test"
            mgr = TmuxManager(session_name="test")
            assert mgr._server is None
            with patch("ccbot.tmux_manager.libtmux.Server") as MockServer:
                mock_srv = MagicMock()
                MockServer.return_value = mock_srv
                result = mgr.server
                assert result is mock_srv
                MockServer.assert_called_once()

    def test_reuses_healthy_server(self) -> None:
        with patch("ccbot.tmux_manager.config") as mock_config:
            mock_config.tmux_session_name = "test"
            mgr = TmuxManager(session_name="test")
            mock_srv = MagicMock()
            mgr._server = mock_srv
            result = mgr.server
            assert result is mock_srv

    def test_reconnects_on_stale_server(self) -> None:
        with patch("ccbot.tmux_manager.config") as mock_config:
            mock_config.tmux_session_name = "test"
            mgr = TmuxManager(session_name="test")
            stale_srv = MagicMock()
            type(stale_srv).sessions = PropertyMock(
                side_effect=Exception("tmux server dead")
            )
            mgr._server = stale_srv

            with patch("ccbot.tmux_manager.libtmux.Server") as MockServer:
                new_srv = MagicMock()
                MockServer.return_value = new_srv
                result = mgr.server
                assert result is new_srv
                assert mgr._server is new_srv
                MockServer.assert_called_once()
