"""Tests for CLI entry point commands (version, help, status)."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from ccbot.main import main


class TestCLIVersion:
    def test_version_prints_and_exits(self) -> None:
        with patch.object(sys, "argv", ["ccbot", "version"]):
            buf = StringIO()
            with patch("sys.stdout", buf):
                main()
            output = buf.getvalue()
            assert output.startswith("ccbot ")
            assert "\n" in output

    def test_version_contains_semver(self) -> None:
        with patch.object(sys, "argv", ["ccbot", "version"]):
            buf = StringIO()
            with patch("sys.stdout", buf):
                main()
            parts = buf.getvalue().strip().split()
            assert len(parts) == 2
            assert parts[0] == "ccbot"


class TestCLIStatus:
    def test_status_runs_without_crash(self) -> None:
        with patch.object(sys, "argv", ["ccbot", "status"]):
            buf = StringIO()
            with patch("sys.stdout", buf):
                main()
            output = buf.getvalue()
            assert "Config dir:" in output

    def test_status_with_session_map(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CCBOT_DIR", str(tmp_path))
        sm = tmp_path / "session_map.json"
        sm.write_text(
            json.dumps(
                {
                    "ccbot:@0": {
                        "session_id": "abc12345-0000-0000-0000-000000000000",
                        "cwd": "/tmp/test",
                        "window_name": "test",
                    }
                }
            )
        )
        with patch.object(sys, "argv", ["ccbot", "status"]):
            buf = StringIO()
            with patch("sys.stdout", buf):
                main()
            output = buf.getvalue()
            assert "1 entries" in output
            assert "test" in output

    def test_status_no_state_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CCBOT_DIR", str(tmp_path))
        with patch.object(sys, "argv", ["ccbot", "status"]):
            buf = StringIO()
            with patch("sys.stdout", buf):
                main()
            output = buf.getvalue()
            assert "not found" in output


class TestCLIHelp:
    def test_help_flag(self) -> None:
        with patch.object(sys, "argv", ["ccbot", "--help"]):
            buf = StringIO()
            with patch("sys.stdout", buf):
                main()
            output = buf.getvalue()
            assert "Usage:" in output
            assert "ccbot web" in output
            assert "--with-web" in output
            assert "hook" in output
            assert "version" in output
            assert "status" in output

    def test_help_short_flag(self) -> None:
        with patch.object(sys, "argv", ["ccbot", "-h"]):
            buf = StringIO()
            with patch("sys.stdout", buf):
                main()
            assert "Usage:" in buf.getvalue()
