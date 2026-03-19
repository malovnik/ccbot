# Предложения PR для upstream (six-ddc/ccbot)

Логическая группировка изменений из ветки `feat/ru-hardening-deepgram` для подачи отдельных PR.

---

## PR 1: WebSocket Bridge

**Коммиты для cherry-pick:**
```bash
git log --oneline --grep="merge malovlab\|WS bridge\|ws_bridge\|ws_protocol\|terminal_stream\|WebSocket"
```

**Файлы:**
- `src/ccbot/ws_bridge.py` (новый)
- `src/ccbot/ws_protocol.py` (новый)
- `src/ccbot/terminal_stream.py` (новый)
- `src/ccbot/config.py` (ws_* параметры)
- `src/ccbot/session_monitor.py` (multi-callback)
- `src/ccbot/main.py` (web mode, --with-web)
- `src/ccbot/bot.py` (WS bridge startup/shutdown)
- `src/ccbot/hook.py` (_update_hook_path)
- `pyproject.toml` (websockets dependency)
- `.env.example` (WS vars)
- `tests/ccbot/test_ws_protocol.py`
- `tests/ccbot/test_ws_bridge_helpers.py`
- `tests/ccbot/test_terminal_stream.py`

**Описание PR:**
```
## Summary
- Add WebSocket bridge server for web frontend integration
- 26 typed dataclass message types with JSON serialization
- Terminal diff-capture streaming (200ms interval)
- Three modes: `ccbot web` (standalone), `--with-web` (parallel), `CCBOT_WS_ENABLED` (env)

## Security
- HMAC token authentication (timing-safe compare_digest)
- 30-second auth timeout for connections
- Rate limiting: 60 msg/min per connection, max 20 connections
- Path boundary enforcement (allowed_roots on all handlers)
- No server path disclosure (~/relative format)
- Key whitelist for send_key, file upload sanitization

## Test plan
- [ ] 17 WS protocol tests (serialize/parse)
- [ ] 8 terminal stream tests (subscribe/unsubscribe)
- [ ] 8 WS bridge helper tests (display_path, is_path_allowed)
```

---

## PR 2: Security Hardening

**Файлы:**
- `src/ccbot/ws_bridge.py` (path validation, auth timeout, message limits)
- `SECURITY.md` (WS bridge section)

**Описание PR:**
```
## Summary
Fix security vulnerabilities in WS bridge and document security model.

## Fixes
- [HIGH] Add allowed_roots + is_dir() validation to _handle_resume_session
- [HIGH] Replace full server paths with ~/relative in all WS messages
- [MEDIUM] Add 30-second auth timeout (prevents connection slot exhaustion)
- [MEDIUM] Add 4096-char text length limit in send_message
- [LOW] Limit uploaded file names to 255 chars

## Test plan
- [ ] TestIsPathAllowed: within root, at root, outside, multiple roots, similar prefix
- [ ] TestDisplayPath: home relative, home itself, root, tmp
```

---

## PR 3: Bug Fixes (Critical)

**Файлы:**
- `src/ccbot/bot.py` (_cleanup_task global, WS bridge shutdown, input buffer cleanup)
- `src/ccbot/session_monitor.py` (subscription cleanup, pending_tools cleanup, JSONL resilience)
- `src/ccbot/tmux_manager.py` (server reconnect)

**Описание PR:**
```
## Summary
Fix critical bugs affecting shutdown, memory leaks, and resilience.

## Fixes
- [CRITICAL] _cleanup_task missing `global` in post_init — file cleanup task never cancelled
- [CRITICAL] WS bridge not stopped in post_shutdown
- [HIGH] Terminal subscriptions not unsubscribed on WS client disconnect (capture task leak)
- [HIGH] tmux server reconnect on stale connection (server property with probe)
- [HIGH] Malformed JSONL lines block monitoring forever → now skip with warning
- [MEDIUM] _pending_tools, _working_status_active not cleaned on session removal
- [MEDIUM] _auto_named_topics grows without cleanup → discard on unbind/kill
- [MEDIUM] _input_buffer not cancelled on unbind → messages sent to dead windows

## Test plan
- [ ] TestTmuxReconnect: first access, reuse, stale reconnect
- [ ] TestCancelInputBuffer: empty, pending, active timer, isolation
- [ ] TestClearPollingState: idle tracking, window state, missing keys
```

---

## PR 4: Performance (blocking FS → threads)

**Файлы:**
- `src/ccbot/session_monitor.py` (scan_projects, _load_current_session_map)
- `src/ccbot/session.py` (load_session_map)

**Описание PR:**
```
## Summary
Move filesystem-heavy operations to threads to prevent event loop blocking.

## Changes
- scan_projects() → _scan_projects_sync() in asyncio.to_thread
- load_session_map() → asyncio.to_thread(Path.read_text)
- _load_current_session_map() → _load_current_session_map_sync() in asyncio.to_thread
- Race condition fix: replace exists()+iterdir() with try/except

## Impact
Prevents event loop stalls during 2-second poll cycles, especially
noticeable on NFS/network-mounted filesystems or with many projects.
```

---

## PR 5: Code Quality

**Файлы:**
- `src/ccbot/handlers/message_queue.py` (_ensure_formatted dedup)
- `src/ccbot/session_monitor.py` (_SENDABLE_EXTS, status emit dedup, import sorting)
- `src/ccbot/ws_bridge.py` (_is_path_allowed helper, _display_path)
- `src/ccbot/session.py` (redundant pass removal)
- `src/ccbot/handlers/status_polling.py` (clear_polling_state, docstring fix)

**Описание PR:**
```
## Summary
- Deduplicate _ensure_formatted (was in message_queue + message_sender)
- Unify _SENDABLE_EXTS between session_monitor and ws_bridge
- Deduplicate status emit branches in session_monitor
- Extract _is_path_allowed() and _display_path() helpers
- Fix STATUS_POLL_INTERVAL docstring (1s → 3s)
- Fix import sorting (ruff I001)
- Add py.typed marker (PEP 561)
- Restore lost CCBOT_SHOW_TOOL_CALLS feature
```

---

## PR 6: Documentation (Russian)

**Файлы:**
- `README_RU.md`
- `docs/ARCHITECTURE.md`
- `docs/DEPLOYMENT.md`
- `docs/FEATURES.md`
- `CHANGELOG.md`
- `CLAUDE.md`
- `SECURITY.md`
- `.env.example`

**Описание PR:**
```
## Summary
Comprehensive Russian documentation for the project.

- README_RU.md: quick start, all commands, all env vars
- ARCHITECTURE.md: system diagram, 26 modules, data flows
- DEPLOYMENT.md: requirements, installation, troubleshooting
- FEATURES.md: all features with usage instructions
- Complete .env.example with all 23 config variables
```

---

## PR 7: Scripts (macOS)

**Файлы:**
- `scripts/start.sh` (новый)
- `scripts/stop.sh` (новый)
- `scripts/restart.sh` (переписан)

**Описание PR:**
```
## Summary
macOS-compatible management scripts.

- Rewrite restart.sh: replace Linux-only pstree with macOS ps -g
- Add start.sh: full startup with dependency check and hook install
- Add stop.sh: graceful shutdown
```

---

## Порядок подачи PR

1. **PR 3 (Bug Fixes)** — самый ценный, исправляет реальные баги
2. **PR 4 (Performance)** — чистое улучшение без риска
3. **PR 5 (Code Quality)** — мелкие улучшения, легко ревьюить
4. **PR 7 (Scripts)** — независимый, полезный
5. **PR 1 (WS Bridge)** — большой, но изолированный
6. **PR 2 (Security)** — зависит от PR 1
7. **PR 6 (Docs)** — последний, когда код стабилен
