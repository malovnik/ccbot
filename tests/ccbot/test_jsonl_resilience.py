"""Tests for JSONL parse resilience in session_monitor._read_new_lines."""

import json

from ccbot.transcript_parser import TranscriptParser


class TestTranscriptParserResilience:
    """Verify parse_line handles edge cases without crashing."""

    def test_valid_assistant_message(self) -> None:
        line = json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Hello"}]},
                "timestamp": "2026-03-20T00:00:00Z",
            }
        )
        result = TranscriptParser.parse_line(line)
        assert result is not None

    def test_valid_user_message(self) -> None:
        line = json.dumps(
            {
                "type": "user",
                "message": {"content": [{"type": "text", "text": "Hi"}]},
                "timestamp": "2026-03-20T00:00:00Z",
            }
        )
        result = TranscriptParser.parse_line(line)
        assert result is not None

    def test_invalid_json_returns_none(self) -> None:
        assert TranscriptParser.parse_line("not json at all") is None

    def test_empty_string_returns_none(self) -> None:
        assert TranscriptParser.parse_line("") is None

    def test_system_type_returns_dict(self) -> None:
        """parse_line returns raw dict for any valid JSON; type filtering is caller's job."""
        line = json.dumps({"type": "system", "data": "init"})
        result = TranscriptParser.parse_line(line)
        assert result is not None
        assert result["type"] == "system"

    def test_missing_message_field_returns_dict(self) -> None:
        """parse_line doesn't validate structure — returns raw dict."""
        line = json.dumps({"type": "assistant", "timestamp": "2026-03-20T00:00:00Z"})
        result = TranscriptParser.parse_line(line)
        assert result is not None

    def test_empty_content_list_returns_dict(self) -> None:
        line = json.dumps(
            {
                "type": "assistant",
                "message": {"content": []},
                "timestamp": "2026-03-20T00:00:00Z",
            }
        )
        result = TranscriptParser.parse_line(line)
        assert result is not None

    def test_truncated_json(self) -> None:
        line = '{"type": "assistant", "message": {"content": [{"typ'
        result = TranscriptParser.parse_line(line)
        assert result is None

    def test_unicode_content(self) -> None:
        line = json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Привет мир 🌍"}]},
                "timestamp": "2026-03-20T00:00:00Z",
            }
        )
        result = TranscriptParser.parse_line(line)
        assert result is not None

    def test_tool_use_message(self) -> None:
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_123",
                            "name": "Read",
                            "input": {"file_path": "/tmp/test.py"},
                        }
                    ]
                },
                "timestamp": "2026-03-20T00:00:00Z",
            }
        )
        result = TranscriptParser.parse_line(line)
        assert result is not None
