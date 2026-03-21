# RM-00: Architecture Review & Scaling Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit the entire CCBot architecture, document design decisions (ADR), and prepare for refactoring (RM-02..05), WebSocket merge (RM-11), and auto-approve watcher (RM-10).

**Architecture:** CCBot is a Telegram-to-tmux bridge: 16 core modules + 9 handlers, ~8300 LOC, bot.py god object (1931 lines). 4 singletons, 3 JSON state files, acyclic dependency graph. This task produces ONLY documents, zero code changes.

**Tech Stack:** Python 3.12, python-telegram-bot, libtmux, asyncio

**Constraints:**
- NO code changes — analysis and documentation only
- NO tests
- All code analysis through Serena (NOTE: Python must be added to `.serena/project.yml` languages first)
- Commit + push after completion

---

### Task 1: Full Architecture Audit via Serena

**Files:**
- Read: `src/ccbot/*.py` (16 files), `src/ccbot/handlers/*.py` (9 files)
- Read: `doc/AUDIT_REPORT.md` (existing dependency graph at lines 129-156)
- Read: `.claude/rules/architecture.md` (existing architecture diagram)

- [ ] **Step 1: Verify Serena Python support is active**

Ensure `.serena/project.yml` has `python` in languages list. If not, add it and restart language server.

```bash
grep -A2 "languages:" .serena/project.yml
# Expected: - typescript \n - python
```

- [ ] **Step 2: Get symbols overview for all 16 core modules**

Run `get_symbols_overview` for each file in `src/ccbot/`:
- `bot.py` (1931 lines — THE god object, expect ~50+ functions)
- `session.py` (893 lines — SessionManager dataclass)
- `transcript_parser.py` (762 lines — JSONL parsing)
- `session_monitor.py` (526 lines — polling loop)
- `tmux_manager.py` (447 lines — TmuxManager class)
- `terminal_parser.py` (365 lines — UI pattern detection)
- `screenshot.py` (336 lines — ANSI→PNG)
- `hook.py` (276 lines — SessionStart hook)
- `markdown_v2.py` (205 lines — MD→MarkdownV2)
- `config.py` (130 lines — Config singleton)
- `monitor_state.py` (109 lines — byte offset tracking)
- `telegram_sender.py` (69 lines — message splitting)
- `main.py` (65 lines — CLI entry)
- `transcribe.py` (56 lines — voice→text)
- `utils.py` (72 lines — atomic_write_json, ccbot_dir)
- `__init__.py`

Record top-level symbol counts per module.

- [ ] **Step 3: Get symbols overview for all 9 handler modules**

Run `get_symbols_overview` for each file in `src/ccbot/handlers/`:
- `message_queue.py` (695 lines)
- `directory_browser.py` (256 lines)
- `interactive_ui.py` (255 lines)
- `history.py` (232 lines)
- `status_polling.py` (204 lines)
- `message_sender.py` (198 lines)
- `response_builder.py` (97 lines)
- `callback_data.py` (51 lines)
- `cleanup.py` (49 lines)

- [ ] **Step 4: Verify dependency graph from AUDIT_REPORT is still accurate**

For each edge in the graph (AUDIT_REPORT.md lines 129-156), verify with `find_referencing_symbols` or `search_for_pattern` on import statements:

```python
# Expected key edges to verify:
# bot.py → ALL modules (confirmed by reading imports)
# session.py → tmux_manager, transcript_parser, utils
# session_monitor.py → config, monitor_state, tmux_manager, transcript_parser, utils
# message_queue.py → markdown_v2, session, terminal_parser, tmux_manager, message_sender
```

If any edges changed, note differences.

- [ ] **Step 5: Record findings in Serena memory**

```
write_memory("rm00-architecture-audit", "Full audit: 25 modules, 8298 LOC, bot.py=1931 lines (god object). Dependency graph verified [date]. [list any discrepancies found]")
```

---

### Task 2: Singleton & DI Analysis

**Files:**
- Read: `src/ccbot/config.py:130` — `config = Config()`
- Read: `src/ccbot/tmux_manager.py:447` — `tmux_manager = TmuxManager()`
- Read: `src/ccbot/session.py:893` — `session_manager = SessionManager()`
- Read: `src/ccbot/transcribe.py:17` — `_client` lazy httpx

- [ ] **Step 1: Audit each singleton's initialization pattern**

For each singleton, document:
1. Where it's instantiated (module-level vs lazy)
2. What side effects happen at import time
3. What can crash (and how — ref AUDIT_REPORT C-2, C-3)
4. Who imports it (count consumers via `find_referencing_symbols`)

Expected findings:
- `config`: module-level, crashes on missing env vars (C-2)
- `session_manager`: module-level, sync file I/O in `__post_init__` (C-3)
- `tmux_manager`: module-level, lazy server init (safe)
- `_client`: lazy on first call (safe)

- [ ] **Step 2: Count singleton consumers**

```
search_for_pattern("from .config import config")  → count files
search_for_pattern("from .tmux_manager import tmux_manager")  → count files
search_for_pattern("from .session import session_manager")  → count files
search_for_pattern("from .transcribe import")  → count files
```

- [ ] **Step 3: Evaluate DI vs Singletons decision**

Use Sequential Thinking MCP to reason through:

**FOR singletons (current):**
- Simple, zero boilerplate
- CCBot is single-user, single-process — no need for DI
- Refactoring to DI would touch EVERY import in 25 files — massive blast radius
- No testing requirement (tests forbidden per roadmap)

**FOR DI:**
- Testability (but tests are forbidden)
- Multi-instance support (not needed — 1 bot per tmux server)
- Cleaner architecture (but higher complexity)

**Expected verdict: KEEP singletons.** Fix crash bugs (C-2, C-3) with defensive coding, not DI migration.

- [ ] **Step 4: Document verdict with reasoning**

Write section in ADR document (Task 4).

---

### Task 3: State Files & Data Flow Analysis

**Files:**
- Read: `src/ccbot/config.py:67-70` — state file paths
- Read: `src/ccbot/session.py` — state.json read/write
- Read: `src/ccbot/hook.py` — session_map.json write
- Read: `src/ccbot/monitor_state.py` — monitor_state.json read/write
- Read: `src/ccbot/utils.py:24-49` — atomic_write_json

- [ ] **Step 1: Map all state file operations**

For each state file, document:

**`state.json`** (~/.ccbot/state.json):
- Written by: `SessionManager._save_state()` via `atomic_write_json`
- Read by: `SessionManager._load_state()` at init
- Contents: thread_bindings, window_states, display_names, read_offsets
- Concurrency: single writer (bot process), no locking needed
- Risk: C-3 (OSError not caught on load)

**`session_map.json`** (~/.ccbot/session_map.json):
- Written by: `hook.py` (separate process — Claude Code child)
- Read by: `session_monitor.py` each poll cycle
- Contents: tmux_session:window_id → {session_id, cwd, window_name}
- Concurrency: writer = hook process, reader = bot process — RACE CONDITION possible
- Protection: `atomic_write_json` in hook, but reader has no locking

**`monitor_state.json`** (~/.ccbot/monitor_state.json):
- Written by: `MonitorState.save()` via `atomic_write_json`
- Read by: `MonitorState._load()` at init
- Contents: file_path → byte_offset mapping
- Concurrency: single writer (bot process)

- [ ] **Step 2: Evaluate JSON vs SQLite**

Use Sequential Thinking MCP:

**FOR JSON (current):**
- 3 small files (<10KB each), rarely written
- `atomic_write_json` already provides crash safety
- No concurrent writers on same file (except session_map — hook vs monitor)
- SQLite would add dependency and complexity for no gain

**FOR SQLite:**
- Better concurrent access (WAL mode)
- But: only session_map has cross-process access, and atomic rename is sufficient
- Overhead of SQLite for 3 tiny files is unjustified

**Expected verdict: KEEP JSON.** Document session_map race window (hook writes, monitor reads) — atomic rename makes this safe on POSIX.

- [ ] **Step 3: Document data flow diagram**

Create a clear data flow showing:
```
hook.py ──write──> session_map.json ──read──> session_monitor.py
bot.py  ──write──> state.json       ──read──> session.py (init)
bot.py  ──write──> monitor_state.json ──read──> monitor_state.py (init)
```

- [ ] **Step 4: Record findings in Serena memory**

```
write_memory("rm00-state-files-analysis", "3 JSON state files, all use atomic_write_json. No SQLite needed. session_map.json has cross-process access (hook writes, monitor reads) — safe due to atomic rename on POSIX.")
```

---

### Task 4: Create Architecture Decision Records (ADR)

**Files:**
- Create: `doc/ARCHITECTURE_DECISIONS.md`

- [ ] **Step 1: Write ADR document**

Create `doc/ARCHITECTURE_DECISIONS.md` with the following structure:

```markdown
# CCBot — Architecture Decision Records

> Updated: 2026-03-21 (RM-00)

## ADR-001: Singletons vs Dependency Injection

**Status:** DECIDED — Keep singletons
**Context:** [from Task 2 analysis]
**Decision:** [verdict + reasoning]
**Consequences:** [what this means for RM-01..14]

## ADR-002: JSON State Files vs SQLite

**Status:** DECIDED — Keep JSON
**Context:** [from Task 3 analysis]
**Decision:** [verdict + reasoning]
**Consequences:** [what this means]

## ADR-003: bot.py Decomposition Target Structure

**Status:** DECIDED — Extract 4 handler modules
**Context:** bot.py = 1931 lines, god object with commands, text handling, callbacks, session lifecycle all mixed
**Decision:** Extract into:
  - handlers/command_handlers.py (~300 lines) — /history, /screenshot, /esc, /kill, /start
  - handlers/text_handler.py (~400 lines) — text_handler, handle_new_message, photo, voice
  - handlers/callback_handler.py (~300 lines) — callback_handler routing all CB_* prefixes
  - handlers/session_lifecycle.py (~400 lines) — _create_and_bind_window, topic handlers
  - bot.py remains as wiring-only (~250 lines) — Application setup, handler registration
**Consequences:** RM-02..05 execute this in 4 sequential chunks

## ADR-004: WebSocket Integration Architecture

**Status:** DECIDED — Parallel asyncio task
**Context:** 3 WS modules from malovlab/ccbot (ws_bridge.py, ws_protocol.py, terminal_stream.py)
**Decision:** WS server runs as asyncio task alongside Telegram bot. Shares session_manager and tmux_manager singletons. Auth via HMAC token.
**Consequences:** RM-11 merges modules, bot.py wiring starts WS server

## ADR-005: Auto-Approve Watcher Architecture

**Status:** DECIDED — Async class with per-window control
**Context:** External bash watcher.sh (45 lines) polls tmux panes for permission prompts
**Decision:** Python async AutoApproveWatcher class, integrated into session_lifecycle, toggle from Telegram per-window
**Consequences:** RM-10 implements after RM-09 (--dangerously-skip-permissions)
```

- [ ] **Step 2: Verify ADR completeness**

Check that each ADR has: Status, Context, Decision, Consequences. All 5 ADRs cover the key architectural decisions for the full roadmap.

- [ ] **Step 3: Commit checkpoint**

```bash
git add doc/ARCHITECTURE_DECISIONS.md
git commit -m "RM-00: add Architecture Decision Records (5 ADRs)"
```

---

### Task 5: Update .claude/rules/architecture.md

**Files:**
- Modify: `.claude/rules/architecture.md`

- [ ] **Step 1: Read current architecture.md**

Verify current content matches actual code structure. Key things to check:
- Module list matches actual files in src/ccbot/
- Handler list matches actual files in src/ccbot/handlers/
- State files section is accurate
- Key design decisions section is up to date

- [ ] **Step 2: Add planned changes section**

Append to `.claude/rules/architecture.md`:

```markdown
## Planned Changes (Roadmap RM-00..14)

### bot.py Decomposition (RM-02..05)
bot.py (1931 lines) will be split into:
- handlers/command_handlers.py — /history, /screenshot, /esc, /kill, /start
- handlers/text_handler.py — text_handler, handle_new_message, photo, voice
- handlers/callback_handler.py — callback routing (all CB_* prefixes)
- handlers/session_lifecycle.py — window creation, topic handlers
- bot.py — wiring only (~250 lines)

### WebSocket Server (RM-11)
New modules from malovlab/ccbot:
- ws_protocol.py — 14 client→server + 13 server→client dataclasses
- terminal_stream.py — diff-based terminal capture (200ms)
- ws_bridge.py — WS server: auth (HMAC), sessions, history, messages

### Auto-Approve Watcher (RM-10)
New module:
- auto_approve.py — async watcher polling tmux panes for permission prompts
```

- [ ] **Step 3: Record completion and commit**

```bash
git add .claude/rules/architecture.md
git commit -m "RM-00: update architecture rules with planned changes"
```

```
write_memory("rm00-architecture-decisions", "ADR-001: Keep singletons. ADR-002: Keep JSON. ADR-003: bot.py → 4 handler modules + wiring. ADR-004: WS as asyncio task. ADR-005: AutoApproveWatcher async class.")
```

---

### Task 6: Final Verification & Push

**Files:**
- Modify: `doc/RM Chunks/RM-00-architecture-review.md` — mark subtasks [x]
- Modify: `doc/RM Chunks/README.md` — mark RM-00 [x]

- [ ] **Step 1: Verify all deliverables exist**

```bash
# ADR document exists and has content
test -s doc/ARCHITECTURE_DECISIONS.md && echo "OK" || echo "MISSING"

# Architecture rules updated
grep "Planned Changes" .claude/rules/architecture.md && echo "OK" || echo "MISSING"
```

- [ ] **Step 2: Update RM-00 chunk status**

In `doc/RM Chunks/RM-00-architecture-review.md`: change all `[ ]` to `[x]`
In `doc/RM Chunks/README.md`: change `- [ ] RM-00` to `- [x] RM-00`

- [ ] **Step 3: Verify documentation accuracy**

Check `doc/FULL_DOCUMENTATION.md` — architecture section should reference the new ADR doc.

- [ ] **Step 4: Final commit and push**

```bash
git add -A doc/RM\ Chunks/ doc/ARCHITECTURE_DECISIONS.md .claude/rules/architecture.md
git commit -m "RM-00: architecture review and scaling plan"
git push
```

- [ ] **Step 5: Record in Serena memory**

```
write_memory("rm00-completed", "RM-00 done 2026-03-21. 5 ADRs written. Key decisions: keep singletons, keep JSON, decompose bot.py into 4 modules + wiring. Ready for RM-01.")
```
