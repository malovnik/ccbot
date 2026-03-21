# CCBot — Architecture Decision Records

> **Updated:** 2026-03-21 (RM-00: Architecture Review)
> **Context:** Pre-refactoring decisions for roadmap RM-00..14

---

## ADR-001: Singletons vs Dependency Injection

**Status:** DECIDED — Keep singletons

**Context:**
CCBot uses 4 module-level singletons consumed across 25 files:
- `config` (config.py:130) — 7 consumers, crashes on missing env vars (C-2)
- `tmux_manager` (tmux_manager.py:447) — 7 consumers, lazy server init
- `session_manager` (session.py:893) — 6 consumers, sync file I/O at init (C-3)
- `_client` (transcribe.py:17) — 1 consumer, lazy httpx on first call

DI container was considered for testability and multi-instance support.

**Decision:** Keep singletons. Rationale:
1. CCBot is single-user, single-process — no need for multi-instance
2. Tests are out of scope for this roadmap (and project philosophy)
3. DI migration would touch imports in all 25 files — massive blast radius for zero practical gain
4. Crash bugs (C-2, C-3) are fixable with defensive coding in specific locations

**Consequences:**
- RM-01 fixes C-2 (config crash) with try/except around `Config()` — NOT with DI
- RM-01 fixes C-3 (session.py OSError) with try/except in `_load_state()` — NOT with DI
- Future multi-user support (if ever needed) would require revisiting this decision

---

## ADR-002: JSON State Files vs SQLite

**Status:** DECIDED — Keep JSON files

**Context:**
3 JSON state files, all using `atomic_write_json` (temp file + `os.replace`):
- `state.json` (~/.ccbot/) — thread bindings, window states. Single writer (bot process).
- `session_map.json` (~/.ccbot/) — hook-generated mapping. Cross-process: hook writes, monitor reads.
- `monitor_state.json` (~/.ccbot/) — byte offsets. Single writer (bot process).

All files are small (<10KB), rarely written (state.json on bind/unbind, session_map on session start, monitor_state each poll cycle).

**Decision:** Keep JSON. Rationale:
1. `atomic_write_json` already provides crash safety via temp+rename
2. `session_map.json` cross-process access is safe: `os.replace` is atomic on POSIX, reader gets either old or new version — never corrupt
3. No concurrent writers on any single file
4. SQLite adds a dependency and WAL/locking complexity for 3 tiny files — unjustified

**Consequences:**
- No migration needed
- session_map.json race window is acceptable (hook writes atomically, monitor reads periodically)
- If CCBot ever becomes multi-process with shared writes, revisit this

---

## ADR-003: bot.py Decomposition — Target Module Structure

**Status:** DECIDED — Extract 4 handler modules

**Context:**
`bot.py` is 1931 lines — a god object containing:
- Command handlers (/start, /history, /screenshot, /esc, /kill)
- Text/photo/voice message handlers
- Callback query routing (all CB_* prefixes)
- Session lifecycle (window creation, topic open/close/edit)
- Application wiring (handler registration, startup/shutdown)

This makes the file impossible to navigate, review, or modify safely.

**Decision:** Extract into 4 new modules in `src/ccbot/handlers/`:

| Module | Responsibility | Est. Lines |
|--------|---------------|------------|
| `command_handlers.py` | /start, /history, /screenshot, /esc, /kill, forward_command_handler | ~300 |
| `text_handler.py` | text_handler, handle_new_message, photo_handler, voice_handler | ~400 |
| `callback_handler.py` | callback_handler (all CB_* prefix routing) | ~300 |
| `session_lifecycle.py` | _create_and_bind_window, _capture_bash_output, topic handlers | ~400 |

`bot.py` remains as wiring-only (~250 lines): Application setup, handler registration, startup/shutdown hooks.

**Execution order:** RM-02 → RM-03 → RM-04 → RM-05 (sequential, each depends on previous).

**Consequences:**
- After RM-05: bot.py < 300 lines, each new module < 400 lines
- Import paths change: `from .bot import X` → `from .handlers.X import Y`
- All bug fixes (RM-06..08) target post-refactoring file locations
- No API changes to external consumers (Telegram callbacks, hook.py)

---

## ADR-004: WebSocket Server Integration

**Status:** DECIDED — Parallel asyncio task sharing existing singletons

**Context:**
3 WebSocket modules exist in `malovlab/ccbot` (commit `f6fff4a`):
- `ws_protocol.py` (302 lines) — 14 client→server + 13 server→client dataclasses
- `terminal_stream.py` (100 lines) — diff-based terminal capture, 200ms interval
- `ws_bridge.py` (665 lines) — WS server: HMAC auth, session management, history, messages, keys, files, voice, terminal streaming

**Decision:**
1. Copy all 3 modules into `src/ccbot/`
2. WS server runs as `asyncio.create_task()` alongside Telegram bot in `bot.py` wiring
3. WS server shares `session_manager` and `tmux_manager` singletons (no new state layer)
4. Auth: HMAC token via `CCBOT_WS_TOKEN` env var
5. Port: `CCBOT_WS_PORT` env var (default: 8765)
6. Add `websockets` dependency: `uv add websockets`

**Consequences:**
- RM-11 executes the merge after RM-05 (needs clean bot.py wiring)
- Graceful shutdown: WS server stop on SIGTERM alongside Telegram bot
- Future web frontend connects to this WS server
- No protocol changes allowed (compatibility with future frontend)

---

## ADR-005: Auto-Approve Watcher Integration

**Status:** DECIDED — Async Python class with per-window tmux polling

**Context:**
External bash script (`watcher.sh`, 45 lines) polls tmux panes every 2s for Claude Code permission prompts (`.claude/` self-edit). `--dangerously-skip-permissions` (RM-09) covers regular permission prompts but NOT `.claude/` self-edit prompts.

**Decision:**
1. New module `src/ccbot/auto_approve.py` with `AutoApproveWatcher` class
2. Async polling loop per-window (2s interval, 3s cooldown after action)
3. Pattern matching against `tmux_manager.capture_pane()` output
4. Per-window toggle from Telegram via callback button
5. Auto-start on new window creation (configurable via `CCBOT_AUTO_APPROVE` env var)
6. Patterns: "allow Claude to edit its own settings" → Down+Enter, "authorize Claude to modify its config files" → y+Enter

**Consequences:**
- RM-10 implements after RM-09 (depends on dangerous mode flag)
- Replaces external watcher.sh — no more separate process to manage
- Telegram UI gets new toggle button per session
- `callback_handler.py` gets new `CB_WATCHER_TOGGLE` handler
