# System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Telegram Bot (bot.py)                       │
│  - Topic-based routing: 1 topic = 1 window = 1 session             │
│  - /history: Paginated message history (default: latest page)      │
│  - /screenshot: Capture tmux pane as PNG                           │
│  - /esc: Send Escape to interrupt Claude                           │
│  - Send text → Claude Code via tmux keystrokes                     │
│  - Forward /commands to Claude Code                                │
│  - Create sessions via directory browser in unbound topics         │
│  - Tool use → tool result: edit message in-place                   │
│  - Interactive UI: AskUserQuestion / ExitPlanMode / Permission     │
│  - Per-user message queue + worker (merge, rate limit)             │
│  - MarkdownV2 output with auto fallback to plain text              │
├──────────────────────┬──────────────────────────────────────────────┤
│  markdown_v2.py      │  telegram_sender.py                         │
│  MD → MarkdownV2     │  split_message (4096 limit)                 │
│  + expandable quotes │                                             │
├──────────────────────┴──────────────────────────────────────────────┤
│  terminal_parser.py                                                 │
│  - Detect interactive UIs (AskUserQuestion, ExitPlanMode, etc.)    │
│  - Parse status line (spinner + working text)                      │
└──────────┬──────────────────────────────────────────────────────────┘
           │                              │
           │ Notify (NewMessage callback) │ Send (tmux keys)
           │                              │
┌──────────┴──────────────┐    ┌──────────┴──────────────────────┐
│  SessionMonitor         │    │  TmuxManager (tmux_manager.py)  │
│  (session_monitor.py)   │    │  - list/find/create/kill windows│
│  - Poll JSONL every 2s  │    │  - send_keys to pane            │
│  - Detect mtime changes │    │  - capture_pane for screenshot  │
│  - Parse new lines      │    └──────────────┬─────────────────┘
│  - Track pending tools  │                   │
│    across poll cycles   │                   │
└──────────┬──────────────┘                   │
           │                                  │
           ▼                                  ▼
┌────────────────────────┐         ┌─────────────────────────┐
│  TranscriptParser      │         │  Tmux Windows           │
│  (transcript_parser.py)│         │  - Claude Code process  │
│  - Parse JSONL entries │         │  - One window per       │
│  - Pair tool_use ↔     │         │    topic/session        │
│    tool_result         │         └────────────┬────────────┘
│  - Format expandable   │                      │
│    quotes for thinking │              SessionStart hook
│  - Extract history     │                      │
└────────────────────────┘                      ▼
                                    ┌────────────────────────┐
┌────────────────────────┐         │  Hook (hook.py)        │
│  SessionManager        │◄────────│  - Receive hook stdin  │
│  (session.py)          │  reads  │  - Write session_map   │
│  - Window ↔ Session    │  map    │    .json               │
│    resolution          │         └────────────────────────┘
│  - Thread bindings     │
│    (topic → window)    │         ┌────────────────────────┐
│  - Message history     │────────►│  Claude Sessions       │
│    retrieval           │  reads  │  ~/.claude/projects/   │
└────────────────────────┘  JSONL  │  - sessions-index      │
                                   │  - *.jsonl files       │
┌────────────────────────┐         └────────────────────────┘
│  MonitorState          │
│  (monitor_state.py)    │
│  - Track byte offset   │
│  - Prevent duplicates  │
│    after restart       │
└────────────────────────┘

Additional modules:
  screenshot.py       ─ Terminal text → PNG rendering (ANSI color, font fallback)
  transcribe.py       ─ Voice-to-text transcription via OpenAI API (gpt-4o-transcribe)
  main.py             ─ CLI entry point
  utils.py            ─ Shared utilities (ccbot_dir, atomic_write_json)

Handler modules (handlers/):
  message_sender.py   ─ safe_reply/safe_edit/safe_send + rate_limit_send
  message_queue.py    ─ Per-user queue + worker (merge, status dedup)
  status_polling.py   ─ Background status line polling (1s interval)
  response_builder.py ─ Response pagination and formatting
  interactive_ui.py   ─ AskUserQuestion / ExitPlanMode / Permission UI
  directory_browser.py─ Directory selection + session picker UI for new topics
  history.py          ─ Paginated message history (/history command)
  cleanup.py          ─ Topic state cleanup on close/delete
  callback_data.py    ─ Callback data constants

State files (~/.ccbot/ or $CCBOT_DIR/):
  state.json         ─ thread bindings + window states + display names + read offsets
  session_map.json   ─ hook-generated window_id→session mapping
  monitor_state.json ─ poll progress (byte offset) per JSONL file
```

## Key Design Decisions

- **Topic-centric** — Each Telegram topic binds to one tmux window. No centralized session list; topics *are* the session list.
- **Window ID-centric** — All internal state keyed by tmux window ID (e.g. `@0`, `@12`), not window names. Window IDs are guaranteed unique within a tmux server session. Window names are kept as display names via `window_display_names` map. Same directory can have multiple windows.
- **Hook-based session tracking** — Claude Code `SessionStart` hook writes `session_map.json`; monitor reads it each poll cycle to auto-detect session changes.
- **Tool use ↔ tool result pairing** — `tool_use_id` tracked across poll cycles; tool result edits the original tool_use Telegram message in-place.
- **MarkdownV2 with fallback** — All messages go through `safe_reply`/`safe_edit`/`safe_send` which convert via `telegramify-markdown` and fall back to plain text on parse failure.
- **No truncation at parse layer** — Full content preserved; splitting at send layer respects Telegram's 4096 char limit with expandable quote atomicity.
- Only sessions registered in `session_map.json` (via hook) are monitored.
- Notifications delivered to users via thread bindings (topic → window_id → session).
- **Startup re-resolution** — Window IDs reset on tmux server restart. On startup, `resolve_stale_ids()` matches persisted display names against live windows to re-map IDs. Old state.json files keyed by window name are auto-migrated.

## Planned Changes (Roadmap RM-00..14)

> See `doc/ARCHITECTURE_DECISIONS.md` for full ADRs.

### bot.py Decomposition (RM-02..05)
bot.py (1931 lines) will be split into:
- `handlers/command_handlers.py` — /start, /history, /screenshot, /esc, /kill (~300 lines)
- `handlers/text_handler.py` — text_handler, handle_new_message, photo, voice (~400 lines)
- `handlers/callback_handler.py` — callback routing (all CB_* prefixes) (~300 lines)
- `handlers/session_lifecycle.py` — window creation, topic handlers (~400 lines)
- `bot.py` — wiring only (~250 lines)

### New Modules

**auto_approve.py** (RM-10): Async watcher polling tmux panes for `.claude/` permission prompts. Per-window toggle from Telegram.

**ws_protocol.py** (RM-11): 14 client→server + 13 server→client dataclasses for WebSocket protocol.

**terminal_stream.py** (RM-11): Diff-based terminal capture at 200ms intervals, per-window subscriptions.

**ws_bridge.py** (RM-11): WebSocket server — HMAC auth, sessions, history, messages, keys, files, voice, terminal streaming. Runs as parallel asyncio task.
