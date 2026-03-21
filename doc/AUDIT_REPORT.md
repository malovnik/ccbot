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

### H-8: `_capture_bash_output` — double `pass` (bot.py:784-793)
И MarkdownV2 edit, и plain-text fallback фейлят → вывод молча теряется.

### H-9: `safe_reply` re-raises (message_sender.py:146-147)
`safe_reply` re-raises на двойном фейле, в отличие от `safe_send`/`safe_edit` (просто логируют). Inconsistent — необработанный exception в handlers.

### H-10: `_scrub_session_env` — `except Exception: pass` (tmux_manager.py:91-93)
Если `unset_environment` фейлит по другой причине (не "var not set") — `TELEGRAM_BOT_TOKEN` утечёт в Claude Code.

---

## MEDIUM — Code smell

### M-1: ~~`.env.example` не содержит 9 из 14 переменных~~ ✅ ИСПРАВЛЕНО (Ревизия 1/3)
`.env.example` обновлён — все 13 реальных переменных добавлены. Примечание: `CCBOT_SENDER_INTERVAL` НЕ существует в коде — была ошибка аудита.

### M-2: `telegram-bot-features.md:124` — ссылка на `/list` (не существует)
Также утверждает "10 commands registered" — фактически 13.

### M-3: ~~`FULL_DOCUMENTATION.md` — неточности~~ ✅ ИСПРАВЛЕНО (Ревизия 1/3)
- `/kill` помечен как ⚠️ ФАНТОМ
- `model_command()` удалён
- bot.py: "~1930 строк"

### M-4: `monitor_state.py:74` — ненужный lazy import
`from .utils import atomic_write_json` внутри метода без причины. Все остальные модули импортируют на верхнем уровне.

### M-5: `markdown_v2.py:15` — private API import
`from telegramify_markdown import _update_block` — private API, может сломаться при обновлении.

### M-6: `scan_projects` — lossy path reconstruction (session_monitor.py:173-175)
`dir_name.replace("-", "/")` заменяет ВСЕ дефисы — директории с дефисами (`my-project`) неправильно реконструируются.

### M-7: `scripts/restart.sh` — Linux-only
Использует `pstree -a` и `grep -P` — не работает на macOS. Hardcoded `TMUX_SESSION="ccbot"`.

### M-8: CI не измеряет coverage
`pytest-cov` в dev deps, но `--cov` не передаётся в CI pipeline.

### M-9: `_IMAGES_DIR.mkdir()` на уровне модуля (bot.py:559-560)
Без try/except — если filesystem read-only → крах при импорте.

### M-10: ~~`topic_edited_handler` — не задокументирован~~ ✅ ИСПРАВЛЕНО (Ревизия 1/3)
Добавлен в документацию как фича #30 (Topic Name Sync).

### M-11: ~~`_capture_bash_output` — не задокументирован~~ ✅ ИСПРАВЛЕНО (Ревизия 1/3)
Добавлен в key functions bot.py и как фича #40 (`!` Command Bash Output Capture).

---

## LOW — Стиль

### L-1: f-strings vs `%s` в logging — inconsistent
Одни файлы используют `f"..."`, другие `%s` для logging. `%s` предпочтительнее (deferred evaluation).

### L-2: `"noop"` hardcoded string (bot.py:1563)
Единственная callback data без `CB_*` константы.

### L-3: `hook.py` — double import внутри функции (lines 231, 264)
Две отдельные `from .utils import ...` вместо одной.

### L-4: `directory_browser.py:22-24` — лишняя пустая строка между imports

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
└── bot.py ──→ ALL modules + ALL handlers
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
monitor_state.py (near-leaf — lazy import utils)
markdown_v2.py ──→ transcript_parser
```

**Circular imports: НЕТ** — граф ациклический.

---

## Непротестированные критические пути

| Путь | Модуль | Риск |
|------|--------|------|
| `text_handler` — основной routing сообщений | bot.py | Критический — core feature |
| `photo_handler` — загрузка и пересылка фото | bot.py | Высокий |
| `voice_handler` — полный e2e flow | bot.py | Высокий |
| `topic_closed_handler` — close → kill → cleanup | bot.py | Высокий |
| `topic_edited_handler` — rename sync | bot.py | Средний |
| `_create_and_bind_window` — создание окна | bot.py | Критический |
| `_capture_bash_output` — `!` command | bot.py | Средний |
| `TmuxManager` — все tmux операции | tmux_manager.py | Критический (но требует tmux) |
| `resolve_stale_ids()` — startup migration | session.py | Высокий |
| `directory_browser.py` — все UI builders | handlers/ | Средний |
| `screenshot.py` — `text_to_image` | screenshot.py | Средний |

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

1. **Реализовать `/kill` command** или удалить из меню
2. **Обернуть `_IMAGES_DIR.mkdir()` в try/except** (bot.py:559-560)
3. **Заменить `asyncio.get_event_loop()` на `get_running_loop()`** (session.py:476)
4. **Добавить `errors="replace"` к aiofiles.open** (session_monitor.py)
5. **Добавить timeout к `queue.join()`** (bot.py:1744)
6. ~~**Обновить `.env.example`**~~ ✅ СДЕЛАНО — все 13 переменных
7. ~~**Исправить неточности в FULL_DOCUMENTATION.md**~~ ✅ СДЕЛАНО — 3 ревизии
8. **Добавить `--cov` в CI pipeline**
9. **Заменить `_update_block` на стабильный API** или закрепить версию `telegramify-markdown`
