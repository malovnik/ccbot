"""Tests for CLI entry point commands (version, help, hook --install)."""

import sys
from io import StringIO
from unittest.mock import patch

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

    def test_help_short_flag(self) -> None:
        with patch.object(sys, "argv", ["ccbot", "-h"]):
            buf = StringIO()
            with patch("sys.stdout", buf):
                main()
            assert "Usage:" in buf.getvalue()
