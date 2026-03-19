"""Tests for new helper functions added during the Ralph Loop revision."""

from pathlib import Path
from unittest.mock import patch

from ccbot.handlers.status_polling import (
    _exit_detected_at,
    _idle_reminder_sent,
    _last_claude_response,
    _last_user_activity,
    _restart_attempts,
    clear_polling_state,
    record_user_activity,
)
from ccbot.ws_bridge import _display_path, _is_path_allowed


class TestClearPollingState:
    def setup_method(self) -> None:
        _last_user_activity.clear()
        _last_claude_response.clear()
        _idle_reminder_sent.clear()
        _exit_detected_at.clear()
        _restart_attempts.clear()

    def test_clears_idle_tracking(self) -> None:
        record_user_activity(123, 456)
        _last_claude_response[(123, 456)] = 100.0
        _idle_reminder_sent.add((123, 456))

        clear_polling_state(123, 456)

        assert (123, 456) not in _last_user_activity
        assert (123, 456) not in _last_claude_response
        assert (123, 456) not in _idle_reminder_sent

    def test_clears_window_state(self) -> None:
        _exit_detected_at["@5"] = 100.0
        _restart_attempts["@5"] = (2, 100.0)

        clear_polling_state(123, 456, window_id="@5")

        assert "@5" not in _exit_detected_at
        assert "@5" not in _restart_attempts

    def test_no_error_on_missing_keys(self) -> None:
        clear_polling_state(999, 888, window_id="@99")

    def test_without_window_id(self) -> None:
        _exit_detected_at["@5"] = 100.0
        clear_polling_state(123, 456)
        assert "@5" in _exit_detected_at


class TestDisplayPath:
    def test_home_relative(self) -> None:
        home = Path.home()
        result = _display_path(home / "projects" / "ccbot")
        assert result == "~/projects/ccbot"

    def test_home_itself(self) -> None:
        result = _display_path(Path.home())
        assert result == "~"

    def test_non_home_path(self) -> None:
        result = _display_path(Path("/tmp/test"))
        assert result == "/tmp/test"


class TestIsPathAllowed:
    @patch("ccbot.ws_bridge.config")
    def test_path_within_root(self, mock_config) -> None:
        mock_config.allowed_roots = [Path("/home/user")]
        assert _is_path_allowed(Path("/home/user/projects/test")) is True

    @patch("ccbot.ws_bridge.config")
    def test_path_is_root(self, mock_config) -> None:
        mock_config.allowed_roots = [Path("/home/user")]
        assert _is_path_allowed(Path("/home/user")) is True

    @patch("ccbot.ws_bridge.config")
    def test_path_outside_root(self, mock_config) -> None:
        mock_config.allowed_roots = [Path("/home/user")]
        assert _is_path_allowed(Path("/etc/passwd")) is False

    @patch("ccbot.ws_bridge.config")
    def test_multiple_roots(self, mock_config) -> None:
        mock_config.allowed_roots = [Path("/home/user"), Path("/opt/projects")]
        assert _is_path_allowed(Path("/opt/projects/test")) is True
        assert _is_path_allowed(Path("/tmp")) is False

    @patch("ccbot.ws_bridge.config")
    def test_similar_prefix_not_matched(self, mock_config) -> None:
        mock_config.allowed_roots = [Path("/home/user")]
        assert _is_path_allowed(Path("/home/user-evil/data")) is False
