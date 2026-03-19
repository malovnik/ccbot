"""WebSocket bridge server — connects web frontend to CCBot internals.

Provides a WebSocket server that exposes CCBot functionality (sessions,
messaging, terminal capture) to web clients. Runs in the same asyncio
event loop as the Telegram bot, sharing SessionManager and TmuxManager.

Key class: WsBridge — manages connections, auth, and message routing.
"""

from __future__ import annotations

import hmac
import logging
import time
from pathlib import Path
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection

from .terminal_stream import TerminalStreamer

from .config import config
from .session import session_manager
from .session_monitor import NewMessage
from .tmux_manager import tmux_manager
from .ws_protocol import (
    WsAuth,
    WsAuthResult,
    WsBrowseDirectory,
    WsCaptureTerminal,
    WsClientMsg,
    WsCreateSession,
    WsDirectoryListing,
    WsError,
    WsGetHistory,
    WsHistory,
    WsKillSession,
    WsListSessions,
    WsMessage,
    WsPing,
    WsPong,
    WsResumeSession,
    WsSendKey,
    WsSendMessage,
    WsSessionCreated,
    WsSessionEnded,
    WsSessionList,
    WsSubscribeTerminal,
    WsTerminalData,
    WsUnsubscribeTerminal,
    WsUploadFile,
    parse_client_message,
    serialize,
)

logger = logging.getLogger(__name__)

# Rate limit: max messages per minute per connection
_RATE_LIMIT = 60
_RATE_WINDOW = 60.0


class _ClientState:
    """Per-connection state for an authenticated WS client."""

    __slots__ = (
        "ws",
        "authenticated",
        "terminal_subscriptions",
        "_message_timestamps",
        "_pending_upload",
    )

    def __init__(self, ws: ServerConnection) -> None:
        self.ws = ws
        self.authenticated = False
        self.terminal_subscriptions: set[str] = set()
        self._message_timestamps: list[float] = []
        self._pending_upload: tuple[str, str] | None = None  # (window_id, file_name)

    def check_rate_limit(self) -> bool:
        """Return True if within rate limit, False if exceeded."""
        now = time.monotonic()
        self._message_timestamps = [
            t for t in self._message_timestamps if now - t < _RATE_WINDOW
        ]
        if len(self._message_timestamps) >= _RATE_LIMIT:
            return False
        self._message_timestamps.append(now)
        return True


_MAX_CONNECTIONS = 20


class WsBridge:
    """WebSocket bridge server exposing CCBot to web frontends."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._clients: dict[int, _ClientState] = {}
        self._server: Any = None
        self._streamer = TerminalStreamer(on_data=self._on_terminal_data)

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port,
            ping_interval=None,
            ping_timeout=None,
            max_size=2**20,
        )
        logger.info("WS Bridge listening on ws://%s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Shut down the server and all connections."""
        await self._streamer.stop()

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("WS Bridge stopped")

    async def broadcast(self, msg_str: str, *, window_id: str | None = None) -> None:
        """Send a message to all authenticated clients.

        If window_id is given, only send to clients subscribed to that window's
        terminal stream (used for terminal_data messages).
        """
        dead: list[int] = []
        for cid, client in self._clients.items():
            if not client.authenticated:
                continue
            if window_id and window_id not in client.terminal_subscriptions:
                continue
            try:
                await client.ws.send(msg_str)
            except websockets.ConnectionClosed:
                dead.append(cid)
        for cid in dead:
            self._clients.pop(cid, None)

    async def on_new_message(self, msg: NewMessage) -> None:
        """Callback for SessionMonitor — forward Claude messages to WS clients."""
        window_id = ""
        for wid, ws in session_manager.window_states.items():
            if ws.session_id == msg.session_id:
                window_id = wid
                break

        if not window_id:
            return

        # Handle file messages (Write tool detected by SessionMonitor)
        logger.debug(
            "on_new_message: type=%s role=%s file=%s text_len=%d",
            msg.content_type,
            msg.role,
            msg.file_path,
            len(msg.text),
        )
        if msg.content_type == "file" and msg.file_path:
            fpath = Path(msg.file_path).resolve()
            if fpath.exists() and fpath.is_file():
                from .ws_protocol import WsFileMessage

                file_msg = WsFileMessage(
                    window_id=window_id,
                    file_path=str(fpath),
                    file_name=fpath.name,
                    file_size=fpath.stat().st_size,
                    download_url=f"/api/file?path={str(fpath)}",
                )
                await self.broadcast(serialize(file_msg))
            return

        # Strip Telegram-specific markers for web display
        clean_text = msg.text
        clean_text = clean_text.replace("||", "")  # expandable quote sentinels
        clean_text = clean_text.replace(">…", "")  # collapsed quote prefix

        ws_msg = WsMessage(
            window_id=window_id,
            role=msg.role,
            content=clean_text,
            content_type=msg.content_type,
            tool_name=msg.tool_name or "",
            tool_use_id=msg.tool_use_id or "",
        )
        await self.broadcast(serialize(ws_msg))

        # Send status update for tool calls
        if msg.content_type in ("tool_use", "thinking"):
            from .ws_protocol import WsStatus

            status_text = msg.tool_name or "Думаю..."
            if msg.content_type == "tool_use" and msg.tool_name:
                status_text = f"⏳ {msg.tool_name}"
            elif msg.content_type == "thinking":
                status_text = "🧠 Думаю..."
            await self.broadcast(
                serialize(WsStatus(window_id=window_id, text=status_text))
            )
        elif msg.is_complete:
            from .ws_protocol import WsStatusClear

            await self.broadcast(serialize(WsStatusClear(window_id=window_id)))

    # --- Connection handler ---

    async def _handle_connection(self, ws: ServerConnection) -> None:
        """Handle a single WebSocket client connection."""
        if len(self._clients) >= _MAX_CONNECTIONS:
            await ws.close(4003, "Too many connections")
            return

        cid = id(ws)
        client = _ClientState(ws)
        self._clients[cid] = client
        remote = ws.remote_address
        logger.info("WS client connected: %s (id=%d)", remote, cid)

        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    if not client.authenticated:
                        continue
                    await self._handle_binary(client, raw)
                    continue

                msg = parse_client_message(raw)
                if msg is None:
                    await self._send(
                        client, WsError(code="parse_error", message="Invalid message")
                    )
                    continue

                if not client.authenticated and not isinstance(msg, WsAuth):
                    await self._send(
                        client,
                        WsError(code="auth_required", message="Authenticate first"),
                    )
                    continue

                if not client.check_rate_limit():
                    await self._send(
                        client, WsError(code="rate_limit", message="Too many messages")
                    )
                    continue

                logger.debug(
                    "WS recv type=%s from id=%d", getattr(msg, "type", "?"), cid
                )
                await self._dispatch(client, msg)
        except websockets.ConnectionClosed as e:
            logger.debug("WS connection closed: code=%s reason=%s", e.code, e.reason)
        finally:
            client.terminal_subscriptions.clear()
            self._clients.pop(cid, None)
            logger.info("WS client disconnected: %s (id=%d)", remote, cid)

    async def _send(self, client: _ClientState, msg: Any) -> None:
        """Send a typed message to a single client."""
        try:
            await client.ws.send(serialize(msg))
        except websockets.ConnectionClosed:
            pass

    async def _dispatch(self, client: _ClientState, msg: WsClientMsg) -> None:
        """Route a parsed client message to the appropriate handler."""
        match msg:
            case WsAuth():
                await self._handle_auth(client, msg)
            case WsPing():
                await self._send(client, WsPong())
            case WsListSessions():
                await self._handle_list_sessions(client)
            case WsCreateSession():
                await self._handle_create_session(client, msg)
            case WsResumeSession():
                await self._handle_resume_session(client, msg)
            case WsKillSession():
                await self._handle_kill_session(client, msg)
            case WsSendMessage():
                await self._handle_send_message(client, msg)
            case WsSendKey():
                await self._handle_send_key(client, msg)
            case WsGetHistory():
                await self._handle_get_history(client, msg)
            case WsBrowseDirectory():
                await self._handle_browse_directory(client, msg)
            case WsSubscribeTerminal():
                w = await tmux_manager.find_window_by_id(msg.window_id)
                if not w:
                    await self._send(
                        client, WsError(code="not_found", message="Window not found")
                    )
                else:
                    client.terminal_subscriptions.add(msg.window_id)
                    capture = await tmux_manager.capture_pane(
                        msg.window_id, with_ansi=True
                    )
                    if capture:
                        await self._send(
                            client,
                            WsTerminalData(window_id=msg.window_id, data=capture),
                        )
                    self._streamer.subscribe(msg.window_id)
            case WsUnsubscribeTerminal():
                client.terminal_subscriptions.discard(msg.window_id)
                self._streamer.unsubscribe(msg.window_id)
            case WsUploadFile():
                client._pending_upload = (msg.window_id, msg.file_name)
            case WsCaptureTerminal():
                capture = await tmux_manager.capture_pane(msg.window_id, with_ansi=True)
                if capture:
                    await self._send(
                        client, WsTerminalData(window_id=msg.window_id, data=capture)
                    )

    # --- Handlers ---

    async def _handle_auth(self, client: _ClientState, msg: WsAuth) -> None:
        expected = getattr(config, "ws_token", "")
        if not expected:
            # No token configured — allow only if binding to localhost
            if config.ws_host in ("127.0.0.1", "localhost", "::1"):
                client.authenticated = True
                await self._send(client, WsAuthResult(success=True))
                return
            # Non-localhost without token = reject
            logger.warning(
                "WS auth rejected: no CCBOT_WS_TOKEN configured for non-localhost binding"
            )
            await self._send(
                client,
                WsAuthResult(
                    success=False,
                    error="CCBOT_WS_TOKEN required for non-localhost access",
                ),
            )
            await client.ws.close(4001, "Unauthorized")
            return
        if hmac.compare_digest(msg.token.encode(), expected.encode()):
            client.authenticated = True
            await self._send(client, WsAuthResult(success=True))
        else:
            logger.warning("WS auth failed from %s", client.ws.remote_address)
            await self._send(client, WsAuthResult(success=False, error="Invalid token"))
            await client.ws.close(4001, "Unauthorized")

    async def _handle_list_sessions(self, client: _ClientState) -> None:
        windows = await tmux_manager.list_windows()
        sessions = []
        for w in windows:
            ws_state = session_manager.get_window_state(w.window_id)
            sessions.append(
                {
                    "window_id": w.window_id,
                    "name": w.window_name,
                    "cwd": w.cwd,
                    "session_id": ws_state.session_id if ws_state else "",
                    "active": True,
                }
            )
        await self._send(client, WsSessionList(sessions=sessions))

    async def _handle_create_session(
        self, client: _ClientState, msg: WsCreateSession
    ) -> None:
        logger.info("WS create_session: path=%s", msg.path)
        path = Path(msg.path).expanduser().resolve()
        if not path.is_dir():
            await self._send(
                client,
                WsError(code="invalid_path", message=f"Not a directory: {msg.path}"),
            )
            return

        # Enforce ALLOWED_ROOTS boundary
        if not any(
            path == root or str(path).startswith(str(root) + "/")
            for root in config.allowed_roots
        ):
            await self._send(
                client,
                WsError(code="access_denied", message="Path outside allowed roots"),
            )
            return

        success, message, window_name, window_id = await tmux_manager.create_window(
            work_dir=str(path)
        )
        if not success:
            await self._send(client, WsError(code="tmux_error", message=message))
            return

        logger.info(
            "WS session created: window_id=%s name=%s cwd=%s",
            window_id,
            window_name,
            path,
        )

        # Wait for hook to register session (up to 5s)
        await session_manager.wait_for_session_map_entry(window_id, timeout=5.0)

        await self._send(
            client,
            WsSessionCreated(
                window_id=window_id,
                name=window_name,
                cwd=str(path),
            ),
        )

        # Broadcast updated session list to all clients
        await self._handle_list_sessions(client)

    async def _handle_resume_session(
        self, client: _ClientState, msg: WsResumeSession
    ) -> None:
        path = Path(msg.path).expanduser().resolve()

        success, message, window_name, window_id = await tmux_manager.create_window(
            work_dir=str(path),
            resume_session_id=msg.session_id,
        )
        if not success:
            await self._send(client, WsError(code="tmux_error", message=message))
            return

        await self._send(
            client,
            WsSessionCreated(
                window_id=window_id,
                name=window_name,
                cwd=str(path),
            ),
        )

    async def _handle_kill_session(
        self, client: _ClientState, msg: WsKillSession
    ) -> None:
        w = await tmux_manager.find_window_by_id(msg.window_id)
        if not w:
            await self._send(
                client, WsError(code="not_found", message="Window not found")
            )
            return

        await tmux_manager.kill_window(msg.window_id)
        await self.broadcast(
            serialize(WsSessionEnded(window_id=msg.window_id, reason="killed"))
        )

    async def _handle_send_message(
        self, client: _ClientState, msg: WsSendMessage
    ) -> None:
        success, error = await session_manager.send_to_window(msg.window_id, msg.text)
        if not success:
            await self._send(client, WsError(code="send_failed", message=error))

    _ALLOWED_KEYS = frozenset(
        {
            "Escape",
            "Tab",
            "Up",
            "Down",
            "Left",
            "Right",
            "Space",
            "Enter",
            "Home",
            "End",
            "PageUp",
            "PageDown",
            "Delete",
            "Backspace",
            "Insert",
        }
    )

    async def _handle_send_key(self, client: _ClientState, msg: WsSendKey) -> None:
        if msg.key not in self._ALLOWED_KEYS:
            await self._send(
                client, WsError(code="invalid_key", message="Key not allowed")
            )
            return

        w = await tmux_manager.find_window_by_id(msg.window_id)
        if not w:
            await self._send(
                client, WsError(code="not_found", message="Window not found")
            )
            return

        await tmux_manager.send_keys(msg.window_id, msg.key, enter=False, literal=False)

    async def _handle_get_history(
        self, client: _ClientState, msg: WsGetHistory
    ) -> None:
        ws_state = session_manager.get_window_state(msg.window_id)
        if not ws_state or not ws_state.session_id or not ws_state.cwd:
            await self._send(client, WsHistory(window_id=msg.window_id, messages=[]))
            return

        # Read JSONL directly for clean content (not Telegram-formatted)
        session = await session_manager.resolve_session_for_window(msg.window_id)
        if not session or not session.file_path:
            await self._send(client, WsHistory(window_id=msg.window_id, messages=[]))
            return

        messages: list[dict[str, str]] = []
        try:
            import aiofiles

            async with aiofiles.open(session.file_path, "r", encoding="utf-8") as f:
                import json as _json

                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue

                    role = data.get("type", "")
                    if role not in ("user", "assistant"):
                        continue

                    content_blocks = data.get("message", {}).get("content", [])
                    ts = data.get("timestamp", "")

                    # Collect all text blocks into one message per entry
                    text_parts: list[str] = []
                    for block in content_blocks:
                        if isinstance(block, str):
                            text_parts.append(block)
                            continue
                        if not isinstance(block, dict):
                            continue
                        block_type = block.get("type", "")
                        if block_type == "text":
                            text_parts.append(block.get("text", ""))
                        elif block_type == "tool_use":
                            # Flush accumulated text first
                            if text_parts:
                                messages.append(
                                    {
                                        "role": role,
                                        "content": "".join(text_parts),
                                        "content_type": "text",
                                        "tool_name": "",
                                        "timestamp": ts,
                                    }
                                )
                                text_parts = []
                            tool_name = block.get("name", "")
                            tool_input = block.get("input", {})

                            # Detect Write tool → emit file message
                            if tool_name == "Write" and isinstance(tool_input, dict):
                                fpath_str = tool_input.get("file_path", "")
                                if fpath_str:
                                    fpath = Path(fpath_str).expanduser().resolve()
                                    ext = fpath.suffix.lower()
                                    if ext in {
                                        ".md",
                                        ".txt",
                                        ".pdf",
                                        ".docx",
                                        ".html",
                                        ".csv",
                                    }:
                                        messages.append(
                                            {
                                                "role": role,
                                                "content": f"📄 {fpath.name}",
                                                "content_type": "text",
                                                "tool_name": "Write",
                                                "timestamp": ts,
                                                "file_name": fpath.name,
                                                "file_path": str(fpath),
                                                "file_size": str(
                                                    fpath.stat().st_size
                                                    if fpath.exists()
                                                    else 0
                                                ),
                                            }
                                        )
                                        continue

                            summary = f"{tool_name}()"
                            if isinstance(tool_input, dict):
                                first_val = next(iter(tool_input.values()), "")
                                if isinstance(first_val, str) and first_val:
                                    summary = f"{tool_name}({first_val[:60]})"
                            messages.append(
                                {
                                    "role": role,
                                    "content": summary,
                                    "content_type": "tool_use",
                                    "tool_name": tool_name,
                                    "timestamp": ts,
                                }
                            )
                        elif block_type == "thinking":
                            if text_parts:
                                messages.append(
                                    {
                                        "role": role,
                                        "content": "".join(text_parts),
                                        "content_type": "text",
                                        "tool_name": "",
                                        "timestamp": ts,
                                    }
                                )
                                text_parts = []
                            messages.append(
                                {
                                    "role": role,
                                    "content": block.get("thinking", ""),
                                    "content_type": "thinking",
                                    "tool_name": "",
                                    "timestamp": ts,
                                }
                            )

                    # Flush remaining text
                    if text_parts:
                        messages.append(
                            {
                                "role": role,
                                "content": "".join(text_parts),
                                "content_type": "text",
                                "tool_name": "",
                                "timestamp": ts,
                            }
                        )
        except OSError:
            pass

        await self._send(
            client,
            WsHistory(
                window_id=msg.window_id,
                messages=messages,
                page=0,
                total_pages=1,
            ),
        )

    async def _handle_browse_directory(
        self, client: _ClientState, msg: WsBrowseDirectory
    ) -> None:
        path = Path(msg.path).expanduser().resolve()
        if not path.is_dir():
            await self._send(client, WsDirectoryListing(path=msg.path))
            return

        # Enforce ALLOWED_ROOTS boundary
        if not any(
            path == root or str(path).startswith(str(root) + "/")
            for root in config.allowed_roots
        ):
            await self._send(
                client,
                WsError(code="access_denied", message="Path outside allowed roots"),
            )
            return

        try:
            dirs = sorted(
                d.name
                for d in path.iterdir()
                if d.is_dir()
                and (config.show_hidden_dirs or not d.name.startswith("."))
            )
        except (PermissionError, OSError):
            dirs = []

        await self._send(
            client,
            WsDirectoryListing(
                path=str(path),
                dirs=dirs,
                show_hidden=config.show_hidden_dirs,
            ),
        )

    async def _handle_binary(self, client: _ClientState, data: bytes) -> None:
        """Handle binary WebSocket frame.

        If pending_upload is set: save file and forward path to Claude.
        Otherwise: treat as voice audio and transcribe via Deepgram.
        """
        logger.info(
            "WS binary frame: %d bytes, pending_upload=%s",
            len(data),
            client._pending_upload,
        )
        if client._pending_upload:
            window_id, file_name = client._pending_upload
            client._pending_upload = None
            await self._save_uploaded_file(client, window_id, file_name, data)
            return
        try:
            from .transcribe import transcribe_voice

            text = await transcribe_voice(data)
            logger.info(
                "WS voice transcription: %d bytes -> %d chars", len(data), len(text)
            )
        except Exception as e:
            logger.error("WS voice transcription failed: %s", e)
            await self._send(
                client, WsError(code="transcribe_error", message="Transcription failed")
            )
            return

        if not text.strip():
            return

        # Find first active window to send transcribed text
        windows = await tmux_manager.list_windows()
        if not windows:
            await self._send(
                client, WsError(code="no_session", message="Нет активных сессий")
            )
            return

        wid = windows[0].window_id
        success, error = await session_manager.send_to_window(wid, text)
        if not success:
            await self._send(client, WsError(code="send_failed", message=error))
            return

        # Echo transcription back to client as user message
        await self._send(
            client,
            WsMessage(
                window_id=wid,
                role="user",
                content=f'🎤 "{text}"',
                content_type="text",
            ),
        )

    # --- File upload ---

    async def _save_uploaded_file(
        self, client: _ClientState, window_id: str, file_name: str, data: bytes
    ) -> None:
        """Save uploaded file and forward path to Claude session."""
        if len(data) > 50 * 1024 * 1024:
            await self._send(client, WsError(code="file_too_large", message="Max 50MB"))
            return

        upload_dir = config.config_dir / "uploads"
        upload_dir.mkdir(exist_ok=True)

        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in file_name)
        if not safe_name:
            safe_name = "upload"

        file_path = upload_dir / safe_name
        # Avoid collisions
        counter = 1
        while file_path.exists():
            stem = file_path.stem.rsplit("_", 1)[0]
            file_path = upload_dir / f"{stem}_{counter}{file_path.suffix}"
            counter += 1

        file_path.write_bytes(data)
        logger.info(
            "WS file uploaded: %s (%d bytes) -> %s", file_name, len(data), file_path
        )

        # Forward to Claude
        success, error = await session_manager.send_to_window(
            window_id, f"(file uploaded: {file_path})"
        )
        if not success:
            await self._send(
                client, WsError(code="send_failed", message="Failed to forward file")
            )
            return

        await self._send(
            client,
            WsMessage(
                window_id=window_id,
                role="user",
                content=f"📎 {file_name}",
                content_type="text",
            ),
        )

    # --- Terminal streaming ---

    async def _on_terminal_data(self, window_id: str, data: str) -> None:
        """Callback from TerminalStreamer — broadcast to subscribed clients."""
        msg = serialize(WsTerminalData(window_id=window_id, data=data))
        await self.broadcast(msg, window_id=window_id)


# Module-level singleton
ws_bridge: WsBridge | None = None
