"""Tests for WebSocket protocol serialization and parsing."""

import json

from ccbot.ws_protocol import (
    WsAuth,
    WsAuthResult,
    WsCreateSession,
    WsError,
    WsMessage,
    WsPing,
    WsPong,
    WsSendKey,
    WsSendMessage,
    parse_client_message,
    serialize,
)


class TestSerialize:
    def test_serialize_basic(self) -> None:
        msg = WsAuthResult(success=True)
        raw = serialize(msg)
        data = json.loads(raw)
        assert data["type"] == "auth_result"
        assert data["success"] is True

    def test_serialize_with_optional_fields(self) -> None:
        msg = WsAuthResult(success=False, error="bad token")
        data = json.loads(serialize(msg))
        assert data["success"] is False
        assert data["error"] == "bad token"

    def test_serialize_error(self) -> None:
        msg = WsError(code="rate_limit", message="Too many messages")
        data = json.loads(serialize(msg))
        assert data["type"] == "error"
        assert data["code"] == "rate_limit"

    def test_serialize_message(self) -> None:
        msg = WsMessage(window_id="@0", content="hello", role="user")
        data = json.loads(serialize(msg))
        assert data["window_id"] == "@0"
        assert data["role"] == "user"

    def test_serialize_pong(self) -> None:
        msg = WsPong()
        data = json.loads(serialize(msg))
        assert data["type"] == "pong"

    def test_serialize_unicode(self) -> None:
        msg = WsMessage(window_id="@1", content="Привет мир 🌍", role="assistant")
        raw = serialize(msg)
        assert "Привет мир 🌍" in raw


class TestParseClientMessage:
    def test_parse_auth(self) -> None:
        raw = json.dumps({"type": "auth", "token": "secret"})
        msg = parse_client_message(raw)
        assert isinstance(msg, WsAuth)
        assert msg.token == "secret"

    def test_parse_send_message(self) -> None:
        raw = json.dumps({"type": "send_message", "window_id": "@0", "text": "hello"})
        msg = parse_client_message(raw)
        assert isinstance(msg, WsSendMessage)
        assert msg.window_id == "@0"
        assert msg.text == "hello"

    def test_parse_send_key(self) -> None:
        raw = json.dumps({"type": "send_key", "window_id": "@0", "key": "Escape"})
        msg = parse_client_message(raw)
        assert isinstance(msg, WsSendKey)
        assert msg.key == "Escape"

    def test_parse_create_session(self) -> None:
        raw = json.dumps({"type": "create_session", "path": "/tmp/test"})
        msg = parse_client_message(raw)
        assert isinstance(msg, WsCreateSession)
        assert msg.path == "/tmp/test"

    def test_parse_ping(self) -> None:
        raw = json.dumps({"type": "ping"})
        msg = parse_client_message(raw)
        assert isinstance(msg, WsPing)

    def test_parse_invalid_json(self) -> None:
        assert parse_client_message("not json") is None

    def test_parse_unknown_type(self) -> None:
        raw = json.dumps({"type": "unknown_command"})
        assert parse_client_message(raw) is None

    def test_parse_missing_type(self) -> None:
        raw = json.dumps({"token": "abc"})
        assert parse_client_message(raw) is None

    def test_parse_invalid_string_field(self) -> None:
        raw = json.dumps({"type": "send_message", "window_id": 123, "text": "hello"})
        assert parse_client_message(raw) is None

    def test_parse_invalid_offset_field(self) -> None:
        raw = json.dumps(
            {"type": "get_history", "window_id": "@0", "offset": "not_a_number"}
        )
        assert parse_client_message(raw) is None

    def test_parse_extra_fields_ignored(self) -> None:
        raw = json.dumps({"type": "auth", "token": "abc", "extra": "ignored"})
        msg = parse_client_message(raw)
        assert msg is None or isinstance(msg, WsAuth)
