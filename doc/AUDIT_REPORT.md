# CCBot — Полный отчёт аудита

> **Дата:** 2026-03-21
> **Метод:** 4 параллельных агента-аудитора (imports, data flow, error handling, feature completeness)
> **Результат:** 4 критических, 10 высоких, 11 средних, 4 низких находки

---

## Сводка по приоритету

| Приоритет | Кол-во | Категория |
|-----------|--------|-----------|
| CRITICAL | 4 | Краши при запуске или в runtime |
| HIGH | 10 | Вероятные баги |
| MEDIUM | 11 | Code smell, потенциальные проблемы |
| LOW | 4 | Стиль, документация |

---

## CRITICAL — Краши

### C-1: ~~`/kill` команда — фантом~~ ✅ ИСПРАВЛЕНО (RM-01)
**Файл:** `bot.py` — реализована `kill_command()` + `CommandHandler("kill", kill_command)`.
Убивает tmux окно, unbind topic, cleanup state.

### C-2: ~~`config.py:130` — крах при импорте без env vars~~ ✅ НЕ АКТУАЛЬНО (RM-01)
`main.py` уже ловит `ValueError` от `Config()` и показывает user-friendly сообщение. `hook.py` не импортирует config. Тесты вне скоупа. Дополнительный фикс не нужен.

### C-3: ~~`session.py:893` — крах при `OSError` на `state.json`~~ ✅ ИСПРАВЛЕНО (RM-01)
Добавлен `OSError` в except clause `_load_state()`. Аналогичный фикс в `monitor_state.py`.

### C-4: ~~`screenshot.py:170` — `ValueError` от ANSI кодов~~ ✅ ИСПРАВЛЕНО (RM-01)
List comprehension заменён на цикл с try/except ValueError — malformed ANSI коды пропускаются.

---

## HIGH — Вероятные баги

### H-1: ~~Deprecated `asyncio.get_event_loop()`~~ ✅ ИСПРАВЛЕНО (RM-06)
Заменён на `asyncio.get_running_loop()` в session.py.

### H-2: ~~`queue.join()` без timeout~~ ✅ ИСПРАВЛЕНО (RM-06)
Обёрнут в `asyncio.wait_for(queue.join(), timeout=30.0)` в text_handler.py.

### H-3: ~~Photo files не чистятся при ошибке~~ ✅ ИСПРАВЛЕНО (RM-07)
Добавлен cleanup `file_path.unlink()` при фейле `send_to_window` в text_handler.py.

### H-4: ~~`_merge_content_tasks` — fragile `task_done()`~~ ✅ НЕ АКТУАЛЬНО (RM-07)
Логика task_done() корректна: компенсирует counter increment от put_nowait() при возврате не-merged элементов. Хорошо документировано в коде.

### H-5: ~~`UnicodeDecodeError` в session_monitor~~ ✅ ИСПРАВЛЕНО (RM-07)
Добавлен `errors="replace"` в aiofiles.open для JSONL чтения.

### H-6: ~~`list_sessions_for_directory` — race condition~~ ✅ ИСПРАВЛЕНО (RM-06)
`_safe_mtime()` helper с try/except OSError — пропускает удалённые файлы.

### H-7: ~~`hook.py` — `subprocess.run` без timeout~~ ✅ ИСПРАВЛЕНО (RM-06)
Добавлен `timeout=10` + `subprocess.TimeoutExpired` handling.

### H-8: ~~`_capture_bash_output` — double `pass`~~ ✅ ИСПРАВЛЕНО (RM-08)
Inner `pass` заменён на `logger.warning` — теперь видно когда bash capture edit фейлит.

### H-9: ~~`safe_reply` re-raises~~ ✅ ИСПРАВЛЕНО (RM-08)
`safe_reply` теперь логирует и возвращает (не re-raises), консистентно с `safe_edit`/`safe_send`.

### H-10: ~~`_scrub_session_env` — `except Exception: pass`~~ ✅ ИСПРАВЛЕНО (RM-08)
Теперь фильтрует ошибку: "unknown variable"/"not set" = тихий pass, всё остальное = `logger.error` с предупреждением о возможной утечке секрета.

---

## MEDIUM — Code smell

### M-1: ~~`.env.example` не содержит 9 из 14 переменных~~ ✅ ИСПРАВЛЕНО (Ревизия 1/3)
`.env.example` обновлён — все 13 реальных переменных добавлены. Примечание: `CCBOT_SENDER_INTERVAL` НЕ существует в коде — была ошибка аудита.

### M-2: ~~`telegram-bot-features.md:124` — ссылка на `/list` (не существует)~~ ⚠️ ОТЛОЖЕНО
Внешний документ, не часть кодовой базы. Ссылка на `/list` и "10 commands" — неточность исходного описания. Не влияет на работу бота.

### M-3: ~~`FULL_DOCUMENTATION.md` — неточности~~ ✅ ИСПРАВЛЕНО (RM-14)
Полная перезапись: bot.py обновлён как wiring-only (~247 строк), добавлены все 8 новых модулей (command_handlers, text_handler, callback_handler, session_lifecycle, auto_approve, ws_bridge, ws_protocol, terminal_stream), обновлены фичи 41-45, добавлены 5 новых env vars.

### M-4: ~~`monitor_state.py:74` — ненужный lazy import~~ ✅ ИСПРАВЛЕНО (RM-12)
Перенесён `from .utils import atomic_write_json` на уровень модуля.

### M-5: ~~`markdown_v2.py:15` — private API import~~ ✅ ИСПРАВЛЕНО (RM-12)
`telegramify-markdown` закреплён на `~=0.5.4` в pyproject.toml.

### M-6: ~~`scan_projects` — lossy path reconstruction~~ ✅ ИСПРАВЛЕНО (RM-12)
Добавлена проверка `Path(candidate).exists()` перед использованием. Документировано как lossy fallback.

### M-7: ~~`scripts/restart.sh` — Linux-only~~ ⚠️ ОТЛОЖЕНО
Утилитарный скрипт для dev-окружения. Использует `pstree -a` и `grep -P` — не работает на macOS. Не влияет на production работу бота. Фикс по необходимости.

### M-8: ~~CI не измеряет coverage~~ ⚠️ НЕ АКТУАЛЬНО
CI pipeline (`check.yml`) настроен с lint, format, typecheck. Coverage — nice-to-have, не блокирует.

### M-9: ~~`_IMAGES_DIR.mkdir()` на уровне модуля~~ ✅ ИСПРАВЛЕНО (RM-12)
Обёрнут в try/except OSError в text_handler.py.

### M-10: ~~`topic_edited_handler` — не задокументирован~~ ✅ ИСПРАВЛЕНО (Ревизия 1/3)
Добавлен в документацию как фича #30 (Topic Name Sync).

### M-11: ~~`_capture_bash_output` — не задокументирован~~ ✅ ИСПРАВЛЕНО (Ревизия 1/3)
Добавлен в key functions bot.py и как фича #40 (`!` Command Bash Output Capture).

---

## LOW — Стиль

### L-1: ~~f-strings vs `%s` в logging — inconsistent~~ ✅ ИСПРАВЛЕНО (RM-13)
Стандартизировано на lazy `%s` formatting в logging calls.

### L-2: ~~`"noop"` hardcoded string~~ ✅ ИСПРАВЛЕНО (RM-13)
Перенесён в `callback_data.py` как `CB_NOOP`. Используется в callback_handler.py.

### L-3: ~~`hook.py` — double import внутри функции~~ ✅ ИСПРАВЛЕНО (RM-13)
Объединены в один import.

### L-4: ~~`directory_browser.py:22-24` — лишняя пустая строка~~ ✅ ИСПРАВЛЕНО (RM-13)
Удалена.

---

## Граф зависимостей (ключевые модули)

```
utils.py (leaf — zero internal deps)
  ↑
config.py
  ↑
├── tmux_manager.py
├── transcribe.py
├── session.py ──→ tmux_manager, transcript_parser, utils
├── session_monitor.py ──→ config, monitor_state, tmux_manager, transcript_parser, utils
├── auto_approve.py ──→ tmux_manager
├── terminal_stream.py ──→ tmux_manager
├── ws_protocol.py (leaf — zero internal deps)
├── ws_bridge.py ──→ config, session, session_monitor, tmux_manager, ws_protocol, terminal_stream
└── bot.py (wiring) ──→ ALL handler modules + session_monitor + auto_approve + ws_bridge
    ├── handlers/command_handlers.py ──→ config, session, tmux_manager, screenshot, terminal_parser, message_sender, callback_data, interactive_ui, history, auto_approve
    ├── handlers/text_handler.py ──→ config, session, tmux_manager, transcribe, terminal_parser, message_queue, message_sender, directory_browser, interactive_ui, cleanup, callback_data, auto_approve
    ├── handlers/callback_handler.py ──→ config, session, tmux_manager, screenshot, terminal_parser, message_sender, directory_browser, interactive_ui, history, cleanup, callback_data, session_lifecycle
    ├── handlers/session_lifecycle.py ──→ config, session, tmux_manager, auto_approve, cleanup, command_handlers
    ├── handlers/message_queue.py ──→ markdown_v2, session, terminal_parser, tmux_manager, message_sender
    ├── handlers/message_sender.py ──→ markdown_v2, transcript_parser
    ├── handlers/status_polling.py ──→ session, terminal_parser, tmux_manager, interactive_ui, cleanup, message_queue
    ├── handlers/interactive_ui.py ──→ session, terminal_parser, tmux_manager, callback_data, message_sender
    ├── handlers/directory_browser.py ──→ session, config, callback_data
    ├── handlers/history.py ──→ config, session, telegram_sender, transcript_parser, callback_data, message_sender
    ├── handlers/response_builder.py ──→ markdown_v2, telegram_sender, transcript_parser
    └── handlers/cleanup.py ──→ interactive_ui, message_queue

terminal_parser.py (leaf — zero internal deps)
transcript_parser.py (leaf — zero internal deps)
telegram_sender.py (leaf — zero internal deps)
screenshot.py (leaf — zero internal deps)
monitor_state.py (near-leaf — utils)
markdown_v2.py ──→ transcript_parser
```

**Circular imports: НЕТ** — граф ациклический.

---

## Непротестированные критические пути

| Путь | Модуль | Риск |
|------|--------|------|
| `text_handler` — основной routing сообщений | handlers/text_handler.py | Критический — core feature |
| `photo_handler` — загрузка и пересылка фото | handlers/text_handler.py | Высокий |
| `voice_handler` — полный e2e flow | handlers/text_handler.py | Высокий |
| `topic_closed_handler` — close → kill → cleanup | handlers/session_lifecycle.py | Высокий |
| `topic_edited_handler` — rename sync | handlers/session_lifecycle.py | Средний |
| `_create_and_bind_window` — создание окна | handlers/session_lifecycle.py | Критический |
| `_capture_bash_output` — `!` command | handlers/text_handler.py | Средний |
| `callback_handler` — all CB_* routing | handlers/callback_handler.py | Высокий |
| `TmuxManager` — все tmux операции | tmux_manager.py | Критический (но требует tmux) |
| `resolve_stale_ids()` — startup migration | session.py | Высокий |
| `directory_browser.py` — все UI builders | handlers/directory_browser.py | Средний |
| `screenshot.py` — `text_to_image` | screenshot.py | Средний |
| `AutoApproveWatcher._watch_loop` — polling | auto_approve.py | Средний |
| `WsBridge._handle_connection` — WS auth+dispatch | ws_bridge.py | Высокий |

---

## Синглтоны

| Синглтон | Модуль | Инициализация |
|----------|--------|---------------|
| `config` | config.py:130 | Module-level, crashes on missing env |
| `tmux_manager` | tmux_manager.py:447 | Module-level, lazy server init |
| `session_manager` | session.py:893 | Module-level, sync file I/O in `__post_init__` |
| `_client` | transcribe.py:17 | Lazy `httpx.AsyncClient` on first call |

Все потребители используют прямой import (`from .config import config`). DI нет.

---

## Рекомендации (приоритизированные)

1. ~~**Реализовать `/kill` command**~~ ✅ СДЕЛАНО (RM-01) — kill_command() в command_handlers.py
2. ~~**Обернуть `_IMAGES_DIR.mkdir()` в try/except**~~ ✅ СДЕЛАНО (RM-12) — в text_handler.py
3. ~~**Заменить `asyncio.get_event_loop()` на `get_running_loop()`**~~ ✅ СДЕЛАНО (RM-06) — в session.py
4. ~~**Добавить `errors="replace"` к aiofiles.open**~~ ✅ СДЕЛАНО (RM-07) — в session_monitor.py
5. ~~**Добавить timeout к `queue.join()`**~~ ✅ СДЕЛАНО (RM-06) — asyncio.wait_for(timeout=30.0) в text_handler.py
6. ~~**Обновить `.env.example`**~~ ✅ СДЕЛАНО — все переменные включая WS и auto-approve
7. ~~**Исправить неточности в FULL_DOCUMENTATION.md**~~ ✅ СДЕЛАНО (RM-14) — полная перезапись
8. **Добавить `--cov` в CI pipeline** — nice-to-have
9. ~~**Закрепить версию `telegramify-markdown`**~~ ✅ СДЕЛАНО (RM-12) — `~=0.5.4` в pyproject.toml
