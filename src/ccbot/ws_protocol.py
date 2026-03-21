"""WebSocket protocol — typed message definitions for frontend communication.

Defines all message types exchanged between the WS Bridge server and
web frontend clients. Uses dataclasses for type safety and JSON serialization.

Key types:
  - Client messages (WsClientMsg): auth, send_message, create_session, etc.
  - Server messages (WsServerMsg): message, status, session_list, etc.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

# --- Client → Server ---


@dataclass
class WsAuth:
    token: str
    type: Literal["auth"] = "auth"


@dataclass
class WsListSessions:
    type: Literal["list_sessions"] = "list_sessions"


@dataclass
class WsCreateSession:
    path: str
    type: Literal["create_session"] = "create_session"


@dataclass
class WsResumeSession:
    session_id: str
    path: str
    type: Literal["resume_session"] = "resume_session"


@dataclass
class WsKillSession:
    window_id: str
    type: Literal["kill_session"] = "kill_session"


@dataclass
class WsSendMessage:
    window_id: str
    text: str
    type: Literal["send_message"] = "send_message"


@dataclass
class WsSendKey:
    window_id: str
    key: str
    type: Literal["send_key"] = "send_key"


@dataclass
class WsGetHistory:
    window_id: str
    offset: int = 0
    type: Literal["get_history"] = "get_history"


@dataclass
class WsBrowseDirectory:
    path: str
    type: Literal["browse_directory"] = "browse_directory"


@dataclass
class WsSubscribeTerminal:
    window_id: str
    type: Literal["subscribe_terminal"] = "subscribe_terminal"


@dataclass
class WsUnsubscribeTerminal:
    window_id: str
    type: Literal["unsubscribe_terminal"] = "unsubscribe_terminal"


@dataclass
class WsCaptureTerminal:
    window_id: str
    type: Literal["capture_terminal"] = "capture_terminal"


@dataclass
class WsUploadFile:
    window_id: str
    file_name: str
    type: Literal["upload_file"] = "upload_file"


@dataclass
class WsPing:
    type: Literal["ping"] = "ping"


WsClientMsg = (
    WsAuth
    | WsListSessions
    | WsCreateSession
    | WsResumeSession
    | WsKillSession
    | WsSendMessage
    | WsSendKey
    | WsGetHistory
    | WsBrowseDirectory
    | WsSubscribeTerminal
    | WsUnsubscribeTerminal
    | WsCaptureTerminal
    | WsPing
)

# --- Server → Client ---


@dataclass
class WsAuthResult:
    success: bool
    error: str = ""
    type: Literal["auth_result"] = "auth_result"


@dataclass
class WsSessionInfo:
    window_id: str
    name: str
    cwd: str
    session_id: str
    active: bool


@dataclass
class WsSessionList:
    sessions: list[dict[str, Any]] = field(default_factory=list)
    type: Literal["session_list"] = "session_list"


@dataclass
class WsSessionCreated:
    window_id: str
    name: str
    cwd: str
    type: Literal["session_created"] = "session_created"


@dataclass
class WsSessionEnded:
    window_id: str
    reason: str = ""
    type: Literal["session_ended"] = "session_ended"


@dataclass
class WsMessage:
    window_id: str
    role: str
    content: str
    content_type: str = "text"
    tool_name: str = ""
    tool_use_id: str = ""
    timestamp: str = ""
    type: Literal["message"] = "message"


@dataclass
class WsFileMessage:
    window_id: str
    file_path: str
    file_name: str
    file_size: int = 0
    download_url: str = ""
    type: Literal["file"] = "file"


@dataclass
class WsStatus:
    window_id: str
    text: str
    emoji: str = ""
    type: Literal["status"] = "status"


@dataclass
class WsStatusClear:
    window_id: str
    type: Literal["status_clear"] = "status_clear"


@dataclass
class WsInteractiveUi:
    window_id: str
    ui_type: str
    lines: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)
    type: Literal["interactive_ui"] = "interactive_ui"


@dataclass
class WsTerminalData:
    window_id: str
    data: str
    type: Literal["terminal_data"] = "terminal_data"


@dataclass
class WsDirectoryListing:
    path: str
    dirs: list[str] = field(default_factory=list)
    show_hidden: bool = False
    page: int = 0
    total_pages: int = 1
    type: Literal["directory_listing"] = "directory_listing"


@dataclass
class WsHistory:
    window_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    page: int = 0
    total_pages: int = 1
    type: Literal["history"] = "history"


@dataclass
class WsError:
    code: str
    message: str
    type: Literal["error"] = "error"


@dataclass
class WsPong:
    type: Literal["pong"] = "pong"


def serialize(msg: Any) -> str:
    """Serialize a server message dataclass to JSON string."""
    return json.dumps(asdict(msg), ensure_ascii=False)


_CLIENT_MSG_MAP: dict[str, type] = {
    "auth": WsAuth,
    "list_sessions": WsListSessions,
    "create_session": WsCreateSession,
    "resume_session": WsResumeSession,
    "kill_session": WsKillSession,
    "send_message": WsSendMessage,
    "send_key": WsSendKey,
    "get_history": WsGetHistory,
    "browse_directory": WsBrowseDirectory,
    "subscribe_terminal": WsSubscribeTerminal,
    "unsubscribe_terminal": WsUnsubscribeTerminal,
    "capture_terminal": WsCaptureTerminal,
    "upload_file": WsUploadFile,
    "ping": WsPing,
}


def parse_client_message(raw: str) -> WsClientMsg | None:
    """Parse a raw JSON string into a typed client message."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    msg_type = data.get("type")
    cls = _CLIENT_MSG_MAP.get(msg_type)  # type: ignore[arg-type]
    if cls is None:
        return None

    try:
        data.pop("type", None)
        msg = cls(**data)  # type: ignore[return-value]

        # Validate string fields are actually strings
        for field_name in ("window_id", "text", "key", "path", "token", "session_id"):
            val = getattr(msg, field_name, None)
            if val is not None and not isinstance(val, str):
                return None

        # Validate offset is int
        if hasattr(msg, "offset") and not isinstance(msg.offset, int):
            return None

        return msg  # type: ignore[return-value]
    except (TypeError, ValueError):
        logger.warning("Failed to parse client message type=%s", msg_type)
        return None
