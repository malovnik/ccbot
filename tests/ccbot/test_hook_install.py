"""Tests for hook installation flow."""

import json
from pathlib import Path
from unittest.mock import patch

from ccbot.hook import _install_hook


class TestInstallHook:
    def test_fresh_install(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        with patch("ccbot.hook._CLAUDE_SETTINGS_FILE", settings_file):
            with patch("ccbot.hook._find_ccbot_path", return_value="/usr/bin/ccbot"):
                result = _install_hook()

        assert result == 0
        assert settings_file.exists()
        data = json.loads(settings_file.read_text())
        hooks = data["hooks"]["SessionStart"]
        assert len(hooks) == 1
        assert hooks[0]["hooks"][0]["command"] == "/usr/bin/ccbot hook"
        assert hooks[0]["hooks"][0]["timeout"] == 5

    def test_already_installed_same_path(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "/usr/bin/ccbot hook",
                                        "timeout": 5,
                                    }
                                ]
                            }
                        ]
                    }
                }
            )
        )
        with patch("ccbot.hook._CLAUDE_SETTINGS_FILE", settings_file):
            with patch("ccbot.hook._find_ccbot_path", return_value="/usr/bin/ccbot"):
                result = _install_hook()

        assert result == 0

    def test_already_installed_different_path(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "/old/ccbot hook",
                                        "timeout": 5,
                                    }
                                ]
                            }
                        ]
                    }
                }
            )
        )
        with patch("ccbot.hook._CLAUDE_SETTINGS_FILE", settings_file):
            with patch("ccbot.hook._find_ccbot_path", return_value="/new/ccbot"):
                result = _install_hook()

        assert result == 0
        data = json.loads(settings_file.read_text())
        cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert cmd == "/new/ccbot hook"

    def test_install_preserves_existing_settings(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"theme": "dark", "model": "opus"}))
        with patch("ccbot.hook._CLAUDE_SETTINGS_FILE", settings_file):
            with patch("ccbot.hook._find_ccbot_path", return_value="/usr/bin/ccbot"):
                result = _install_hook()

        assert result == 0
        data = json.loads(settings_file.read_text())
        assert data["theme"] == "dark"
        assert data["model"] == "opus"
        assert "SessionStart" in data["hooks"]

    def test_install_creates_parent_dirs(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "deep" / "nested" / "settings.json"
        with patch("ccbot.hook._CLAUDE_SETTINGS_FILE", settings_file):
            with patch("ccbot.hook._find_ccbot_path", return_value="/usr/bin/ccbot"):
                result = _install_hook()

        assert result == 0
        assert settings_file.exists()
