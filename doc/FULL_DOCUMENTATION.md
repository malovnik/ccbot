# CCBot (ccmux) — Полная документация

> **Репозиторий:** github.com/malovnik/ccbot
> **Описание:** Telegram ↔ tmux bridge for Claude Code
> **Стек:** Python 3.12, python-telegram-bot, libtmux, uv
> **Дата аудита:** 2026-03-21

---

## Оглавление

1. [Что это такое](#что-это-такое)
2. [Как работает (простым языком)](#как-работает)
3. [Архитектура](#архитектура)
4. [Конфигурация и переменные окружения](#конфигурация)
5. [Команды бота](#команды-бота)
6. [Модули: подробное описание каждого файла](#модули)
7. [Handlers: подробное описание](#handlers)
8. [State-файлы и персистентность](#state-файлы)
9. [Зависимости](#зависимости)
10. [Тесты](#тесты)
11. [CI/CD](#cicd)
12. [Известные фичи и возможности](#фичи)

---

## 1. Что это такое {#что-это-такое}

CCBot — это Telegram-бот, который позволяет управлять сессиями Claude Code через Telegram. Каждый **Telegram Forum topic** привязывается к одному **tmux окну**, в котором запущен один экземпляр **Claude Code**. Ты пишешь в topic — текст улетает в Claude Code. Claude отвечает — ответ приходит тебе в topic.

**Ключевой принцип:** 1 Topic = 1 tmux Window = 1 Claude Code Session.

---

## 2. Как работает {#как-работает}

### Потоки данных

**Ты → Claude Code:**
```
Пишешь в Telegram topic
  → Бот определяет привязку topic → tmux window
  → Отправляет текст как keystrokes в tmux window
  → Claude Code получает и обрабатывает
```

**Claude Code → Ты:**
```
Claude Code пишет ответ в JSONL файл (~/.claude/projects/...)
  → SessionMonitor каждые 2 секунды читает новые строки
  → Парсит через TranscriptParser
  → Отправляет в Telegram через message queue
```

**Создание новой сессии:**
```
Пишешь в незавязанный topic
  → Появляется Window Picker (если есть свободные окна)
  → Или Directory Browser для выбора папки
  → Или Session Picker для resume существующей сессии
  → Создаётся tmux window + запускается Claude Code
  → SessionStart hook записывает session_map.json
  → Topic привязан к окну
```

---

## 3. Архитектура {#архитектура}

```
┌─────────────────────────────────────────────────────────────────┐
│                    Telegram Bot (bot.py)                         │
│  Handlers: /start, /history, /screenshot, /esc, /kill, /unbind  │
│  + photo_handler, voice_handler, topic_closed_handler           │
│  + callback_query_handler (dir browser, history, interactive)   │
├────────────────────┬────────────────────────────────────────────┤
│  markdown_v2.py    │  telegram_sender.py                       │
│  MD → MarkdownV2   │  split_message (4096 limit)               │
│  + expandable      │                                           │
│    quotes          │                                           │
├────────────────────┴────────────────────────────────────────────┤
│  terminal_parser.py                                             │
│  Detect interactive UIs + parse status line                     │
├─────────────────┬───────────────────────────────────────────────┤
│ SessionMonitor  │  TmuxManager (tmux_manager.py)               │
│ Poll JSONL 2s   │  list/find/create/kill windows               │
│ Detect changes  │  send_keys, capture_pane                     │
├─────────────────┤                                              │
│ TranscriptParser│  Hook (hook.py)                              │
│ Parse JSONL     │  SessionStart → session_map.json             │
│ Tool pairing    │                                              │
├─────────────────┤                                              │
│ SessionManager  │  MonitorState                                │
│ Bindings, state │  Byte offset tracking                        │
└─────────────────┴───────────────────────────────────────────────┘

Handlers (handlers/):
  message_sender.py   — safe_reply/safe_edit/safe_send + fallback
  message_queue.py    — Per-user queue + worker, merge, flood control
  status_polling.py   — Background status (1s), topic cleanup
  response_builder.py — Pagination, content type formatting
  interactive_ui.py   — AskUserQuestion/ExitPlanMode/Permission
  directory_browser.py— Directory selection + session picker
  cleanup.py          — Unified topic state cleanup
  callback_data.py    — CB_* constants
  history.py          — Paginated message history
```

---

## 4. Конфигурация {#конфигурация}

### Переменные окружения

| Переменная | Обязательная | По умолчанию | Описание |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Да | — | Токен Telegram бота от @BotFather |
| `ALLOWED_USERS` | Да | — | Comma-separated Telegram user IDs |
| `TMUX_SESSION_NAME` | Нет | `ccbot` | Имя tmux-сессии |
| `CLAUDE_COMMAND` | Нет | `claude` | Команда запуска Claude Code |
| `MONITOR_POLL_INTERVAL` | Нет | `2.0` | Интервал polling JSONL (секунды) |
| `CCBOT_SHOW_USER_MESSAGES` | Нет | `true` | Показывать сообщения пользователя с prefix |
| `CCBOT_SHOW_TOOL_CALLS` | Нет | `true` | Показывать tool_use/tool_result |
| `CCBOT_SHOW_HIDDEN_DIRS` | Нет | `false` | Показывать скрытые папки в browser |
| `OPENAI_API_KEY` | Нет | — | Для транскрипции голосовых сообщений |
| `OPENAI_BASE_URL` | Нет | `https://api.openai.com/v1` | Base URL для OpenAI API |
| `CCBOT_DIR` | Нет | `~/.ccbot` | Директория конфигурации |
| `CCBOT_CLAUDE_PROJECTS_PATH` | Нет | — | Кастомный путь к проектам Claude |
| `CLAUDE_CONFIG_DIR` | Нет | — | Кастомный config dir Claude |

### Приоритет .env файлов
1. Локальный `.env` (текущая директория)
2. `$CCBOT_DIR/.env` (по умолчанию `~/.ccbot/.env`)

### Безопасность
Чувствительные переменные (`TELEGRAM_BOT_TOKEN`, `ALLOWED_USERS`, `OPENAI_API_KEY`) удаляются из `os.environ` после чтения, чтобы дочерние процессы (Claude Code) не наследовали их. Также чистится tmux session environment.

---

## 5. Команды бота {#команды-бота}

| Команда | Что делает |
|---|---|
| `/start` | Приветственное сообщение |
| `/history` | Показать историю сообщений текущей сессии с пагинацией |
| `/screenshot` | Сделать скриншот терминала (PNG) |
| `/esc` | Отправить Escape в Claude Code (прервать) |
| `/kill` | Убить tmux окно + отвязать topic + очистить state. Подтверждение не требуется. |
| `/unbind` | Отвязать topic от window (без kill) |
| `/usage` | Показать статистику использования Claude Code (парсит TUI вывод) |
| `/clear` | ↗ Forward в Claude Code — очистить историю разговора |
| `/compact` | ↗ Forward в Claude Code — компактировать контекст |
| `/<anything>` | Неизвестные команды перенаправляются в Claude Code через `forward_command_handler` |

> **Примечание:** Команды `/clear`, `/compact` и другие Claude Code команды (CC_COMMANDS) добавляются в меню Telegram автоматически и обрабатываются через `forward_command_handler` — бот просто пересылает их как текст в tmux окно.

### Специальные типы сообщений
- **Фото** → скачивается и путь отправляется в Claude Code
- **Голос** → транскрибируется через OpenAI API → отправляется как текст
- **Стикеры/анимации** → отклоняются с предупреждением

---

## 6. Модули: подробное описание {#модули}

### `src/ccbot/main.py` — Точка входа

**Что делает:** CLI-диспетчер. Два режима:
1. `ccbot hook` → делегирует в `hook.hook_main()`
2. По умолчанию → настраивает логирование, инициализирует tmux, запускает бота

**Функции:**
- `main()` — единственная функция, точка входа из `pyproject.toml`

---

### `src/ccbot/config.py` — Конфигурация

**Что делает:** Singleton `Config`, загружает все env vars, создаёт пути к state-файлам.

**Класс `Config`:**
- `__init__()` — загрузка .env, валидация обязательных переменных, scrub чувствительных
- `is_user_allowed(user_id)` — проверка по allowed_users

**Ключевые атрибуты:**
- `telegram_bot_token`, `allowed_users`, `tmux_session_name`, `claude_command`
- `state_file`, `session_map_file`, `monitor_state_file` — пути к state-файлам
- `claude_projects_path` — путь к ~/.claude/projects/
- `show_user_messages`, `show_tool_calls`, `show_hidden_dirs` — флаги отображения
- `openai_api_key`, `openai_base_url` — для голосовой транскрипции

**Глобальный экземпляр:** `config = Config()`

---

### `src/ccbot/hook.py` — SessionStart Hook

**Что делает:** Вызывается Claude Code при старте сессии. Записывает маппинг window→session в `session_map.json`. Также поддерживает `--install` для автоустановки хука.

**Функции:**
- `hook_main()` — CLI entry. Парсит stdin JSON от Claude Code, определяет tmux pane/window, пишет session_map.json с file locking
- `_install_hook()` — автоустановка хука в `~/.claude/settings.json`
- `_find_ccbot_path()` — поиск ccbot binary (PATH → venv → fallback)
- `_is_hook_installed(settings)` — проверка наличия хука

**Особенности:**
- НЕ импортирует config.py (нет TELEGRAM_BOT_TOKEN в tmux)
- File locking через `fcntl.flock` для конкурентных hook-вызовов
- Чистит old-format ключи (по имени окна вместо ID)
- Валидирует session_id как UUID

---

### `src/ccbot/bot.py` — Основной бот (~1930 строк)

**Что делает:** Регистрирует все хэндлеры, управляет жизненным циклом бота, содержит все command handlers и message routing.

**Ключевые функции:**
- `create_bot()` — создаёт Application с AIORateLimiter, регистрирует handlers
- `post_init()` — вызывается после инициализации бота: resolve_stale_ids, start monitor, start status polling
- `post_shutdown()` — остановка monitor, workers, httpx clients
- `handle_new_message()` — основной handler: routing по topic, directory browser, send_to_window
- `text_handler()` — основной routing текстовых сообщений
- `callback_handler()` — обработка inline keyboard callback'ов
- `start_command()` — /start
- `history_command()` — /history
- `screenshot_command()` — /screenshot (capture pane → PNG)
- `esc_command()` — /esc (отправить Escape в tmux)
- `unbind_command()` — /unbind (отвязать topic)
- `usage_command()` — /usage (capture pane, parse usage modal)
- `forward_command_handler()` — forward неизвестных /commands в Claude Code (включая CC_COMMANDS: clear, compact и др.)
- `photo_handler()` — скачать фото, отправить путь как base64 image
- `voice_handler()` — транскрипция через OpenAI API
- `topic_closed_handler()` — cleanup при закрытии/удалении topic
- `topic_edited_handler()` — синхронизация имени tmux window при переименовании topic
- `unsupported_content_handler()` — предупреждение для стикеров и т.д.
- `_on_new_message()` — callback из SessionMonitor, routing к нужному topic
- `_capture_bash_output()` — polling вывода `!` shell-команд (30s timeout, 1s poll interval)
- `_create_and_bind_window()` — создание tmux окна и привязка к topic

**Rate limiting:**
- `AIORateLimiter(max_retries=5)` на Application (30 req/s global)
- Pre-fill bucket при старте для избежания burst

---

### `src/ccbot/session.py` — Менеджер сессий

**Что делает:** Центральный хаб состояния. Управляет маппингами Window→Session и User→Thread→Window.

**Dataclasses:**
- `WindowState` — session_id, cwd, window_name для каждого окна
- `ClaudeSession` — session_id, summary, message_count, file_path

**Класс `SessionManager`:**
- `_load_state()` / `_save_state()` — персистентность в state.json
- `resolve_stale_ids()` — re-resolve window IDs после рестарта tmux (миграция old format)
- `load_session_map()` — читает session_map.json, обновляет window_states
- `bind_thread()` / `unbind_thread()` — привязка topic к window
- `resolve_window_for_thread()` — lookup window_id по thread_id
- `iter_thread_bindings()` — генератор (user_id, thread_id, window_id)
- `find_users_for_session()` — найти всех пользователей привязанных к session
- `send_to_window()` — отправить текст в tmux window
- `get_recent_messages()` — история сообщений (byte range support)
- `list_sessions_for_directory()` — список Claude сессий для папки
- `resolve_session_for_window()` — window → ClaudeSession
- `resolve_chat_id()` — правильный chat_id для supergroup forum topics
- `set_group_chat_id()` — сохранить group chat_id для topic routing
- `wait_for_session_map_entry()` — polling session_map после создания окна
- `get_window_for_thread()` — sync lookup window_id для user+thread
- `get_display_name()` — получить display name для window ID
- `get_window_state()` — получить WindowState для window
- `clear_window_session()` — очистить session info для window
- `update_display_name()` — обновить display name для window
- `update_user_window_offset()` — обновить per-user read offset для window

**Глобальный экземпляр:** `session_manager = SessionManager()`

---

### `src/ccbot/tmux_manager.py` — Управление tmux

**Что делает:** Обёртка над libtmux для async-операций с tmux.

**Dataclass:**
- `TmuxWindow` — window_id, window_name, cwd, pane_current_command

**Класс `TmuxManager`:**
- `get_or_create_session()` — получить или создать tmux session
- `list_windows()` — список окон (пропускает `__main__`)
- `find_window_by_id()` / `find_window_by_name()` — поиск окна
- `capture_pane()` — захват содержимого (plain text или с ANSI)
- `send_keys()` — отправка текста/клавиш в окно (с задержкой 500ms перед Enter, 1s для `!` commands)
- `rename_window()` — переименование окна
- `kill_window()` — убийство окна
- `create_window()` — создание нового окна + опционально запуск Claude Code (поддержка --resume)
- `get_session()` — получить существующую tmux session (или None)
- `server` — property: lazy-initialized libtmux.Server

**Особенности:**
- Все libtmux вызовы через `asyncio.to_thread()`
- `allow-rename off` для новых окон (Claude Code не перезаписывает имена)
- Автоинкремент имени если дублируется (project-2, project-3...)
- Scrub sensitive env vars из tmux session environment

**Глобальный экземпляр:** `tmux_manager = TmuxManager()`

---

### `src/ccbot/session_monitor.py` — Мониторинг сессий

**Что делает:** Async polling loop: каждые N секунд читает JSONL файлы, парсит новые записи, вызывает callback.

**Dataclasses:**
- `SessionInfo` — session_id, file_path
- `NewMessage` — session_id, text, is_complete, content_type, tool_use_id, role, tool_name, image_data

**Класс `SessionMonitor`:**
- `start()` / `stop()` — управление polling loop
- `set_message_callback()` — установить callback для новых сообщений
- `_monitor_loop()` — основной цикл: load_session_map → detect_changes → check_for_updates
- `check_for_updates()` — проверка всех сессий на новые сообщения
- `_read_new_lines()` — инкрементальное чтение JSONL по byte offset
- `scan_projects()` — сканирование проектов с активными tmux окнами
- `_detect_and_cleanup_changes()` — детекция изменений в session_map
- `_cleanup_all_stale_sessions()` — очистка при старте

**Оптимизации:**
- mtime cache: пропуск неизменённых файлов
- byte offset: чтение только новых строк
- Partial JSONL line recovery: не двигает offset при неполной строке
- File truncation detection: сброс offset при /clear

---

### `src/ccbot/transcript_parser.py` — Парсер JSONL

**Что делает:** Парсит Claude Code JSONL файлы в структурированные сообщения. Tool pairing: tool_use → tool_result через tool_use_id.

**Dataclasses:**
- `ParsedMessage` — message_type, text, tool_name
- `ParsedEntry` — role, text, content_type, tool_use_id, timestamp, tool_name, image_data
- `PendingToolInfo` — summary, tool_name, input_data

**Класс `TranscriptParser` (static methods):**
- `parse_line()` — одна JSONL строка → dict
- `parse_message()` — dict → ParsedMessage (text extraction, local command detection)
- `parse_entries()` — list[dict] → list[ParsedEntry] (полный parsing с tool pairing)
- `format_tool_use_summary()` — форматирование tool_use (Read, Write, Bash, Grep, etc.)
- `extract_tool_result_text()` / `extract_tool_result_images()` — извлечение контента из tool_result
- `_format_tool_result_text()` — форматирование с статистикой (lines, matches, files)
- `_format_edit_diff()` — unified diff для Edit tool
- `_format_expandable_quote()` — сентинелы для expandable blockquotes

**Поддерживаемые content types:**
- `text` — обычный текст
- `thinking` — размышления Claude → expandable quote
- `tool_use` — вызов инструмента → summary line
- `tool_result` — результат инструмента → stats + expandable quote
- `local_command` — /command ответ → formatted code block

**Поддерживаемые tools с форматированием:**
Read, Write, Edit, Bash, Grep, Glob, Task, WebFetch, WebSearch, TodoWrite, TodoRead, AskUserQuestion, ExitPlanMode, Skill, NotebookEdit

---

### `src/ccbot/terminal_parser.py` — Парсер терминала

**Что делает:** Анализирует captured tmux pane text. Детектит interactive UI и status line.

**Dataclasses:**
- `InteractiveUIContent` — content, name
- `UIPattern` — name, top (regexes), bottom (regexes), min_gap
- `UsageInfo` — raw_text, parsed_lines

**UI Patterns (порядок имеет значение, первый match побеждает):**
1. `ExitPlanMode` — "Would you like to proceed?" / "Claude has written up a plan"
2. `AskUserQuestion` (multi-tab) — "← ☐✔☒" (без bottom)
3. `AskUserQuestion` (single-tab) — "☐✔☒" ... "Enter to select"
4. `PermissionPrompt` — "Do you want to proceed?" ... "Esc to cancel"
5. `PermissionPrompt` (numbered) — "❯ 1. Yes" (без bottom)
6. `BashApproval` — "Bash command" / "This command requires approval"
7. `RestoreCheckpoint` — "Restore the code" ... "Enter to continue"
8. `Settings` — "Settings: tab to cycle" / "Select model"

**Функции:**
- `extract_interactive_content()` — извлечь контент interactive UI
- `is_interactive_ui()` — проверка наличия UI
- `parse_status_line()` — извлечь status line (spinner chars + text)
- `strip_pane_chrome()` — убрать chrome (prompt + status bar)
- `extract_bash_output()` — извлечь вывод `!` command
- `parse_usage_output()` — парсинг /usage modal

---

### `src/ccbot/monitor_state.py` — Персистентное состояние мониторинга

**Что делает:** Хранит byte offsets для каждой сессии, чтобы после рестарта не пересылать старые сообщения.

**Dataclasses:**
- `TrackedSession` — session_id, file_path, last_byte_offset
- `MonitorState` — state_file, tracked_sessions, _dirty flag

**Методы:**
- `load()` / `save()` / `save_if_dirty()` — персистентность
- `get_session()` / `update_session()` / `remove_session()` — CRUD

---

### `src/ccbot/markdown_v2.py` — Конвертер Markdown

**Что делает:** MD → Telegram MarkdownV2. Специальная обработка expandable blockquotes и таблиц.

**Функции:**
- `convert_markdown(text)` — основная функция. Извлекает expandable quotes, конвертирует через telegramify_markdown, собирает обратно
- `convert_markdown_tables(text)` — MD таблицы → card-style key-value pairs
- `_markdownify(text)` — обёртка над TelegramMarkdownRenderer (disable indented code blocks)
- `_render_expandable_quote()` — рендер ">...||\|" с truncation (3800 chars max)
- `_escape_mdv2()` — escape спецсимволов MarkdownV2

---

### `src/ccbot/telegram_sender.py` — Разбиение сообщений

**Что делает:** Разбивает длинные тексты на чанки ≤4096 символов для Telegram.

**Функции:**
- `split_message(text, max_length=4096)` — split по newlines, сохраняет code blocks (закрывает ``` в одном чанке, открывает в следующем)

---

### `src/ccbot/screenshot.py` — Скриншоты терминала

**Что делает:** Рендерит text → PNG с ANSI цветами и font fallback chain.

**Font chain:**
1. JetBrains Mono — Latin, symbols
2. Noto Sans Mono CJK SC — CJK characters
3. Symbola — special symbols

**Функции:**
- `text_to_image(text, font_size=28, with_ansi=True)` → PNG bytes
- `_parse_ansi_line()` — парсинг ANSI escape codes
- `_apply_ansi_codes()` — применение цветов (16/256/RGB)
- `_font_tier()` — выбор шрифта по codepoint

**Особенности:**
- CPU-intensive рендеринг в thread pool
- Dark background (#1E1E1E)
- Поддержка всех ANSI цветов (basic 16, 256, RGB)

---

### `src/ccbot/transcribe.py` — Голосовая транскрипция

**Что делает:** Транскрибирует OGG голосовые сообщения через OpenAI API (gpt-4o-transcribe).

**Функции:**
- `transcribe_voice(ogg_data)` → str (текст)
- `close_client()` — закрытие httpx клиента
- `_get_client()` — lazy-initialized httpx singleton

**Особенности:**
- Не требует OpenAI SDK — прямые HTTP запросы через httpx
- Timeout 30 секунд

---

### `src/ccbot/utils.py` — Утилиты

**Функции:**
- `ccbot_dir()` → Path — resolve config directory ($CCBOT_DIR или ~/.ccbot)
- `atomic_write_json(path, data)` — crash-safe запись JSON (temp → rename)
- `read_cwd_from_jsonl(file_path)` — извлечь cwd из первой JSONL записи

---

## 7. Handlers {#handlers}

### `handlers/callback_data.py` — Константы callback data

**CB_* prefixes для inline keyboards:**
- `CB_HISTORY_PREV/NEXT` — пагинация истории (`hp:`, `hn:`)
- `CB_DIR_SELECT/UP/CONFIRM/CANCEL/PAGE` — directory browser (`db:`)
- `CB_WIN_BIND/NEW/CANCEL` — window picker (`wb:`)
- `CB_SCREENSHOT_REFRESH` — обновление скриншота (`ss:ref:`)
- `CB_ASK_UP/DOWN/LEFT/RIGHT/ESC/ENTER/SPACE/TAB/REFRESH` — interactive UI навигация (`aq:`)
- `CB_SESSION_SELECT/NEW/CANCEL` — session picker (`rs:`)
- `CB_KEYS_PREFIX` — screenshot control keys (`kb:`)

---

### `handlers/message_sender.py` — Безопасная отправка

**Что делает:** Обёртки для отправки с MarkdownV2 → plain text fallback.

**Функции:**
- `send_with_fallback(bot, chat_id, text)` → Message | None
- `send_photo(bot, chat_id, image_data)` — single or media group
- `safe_reply(message, text)` — ответ с fallback
- `safe_edit(target, text)` — редактирование с fallback
- `safe_send(bot, chat_id, text)` — отправка с fallback
- `strip_sentinels(text)` — убрать expandable quote маркеры для plain text

**Особенности:**
- Disable link previews
- RetryAfter re-raise для caller handling

---

### `handlers/message_queue.py` — Очередь сообщений

**Что делает:** Per-user FIFO очередь + worker для упорядоченной доставки.

**MessageTask types:**
- `content` — контент от Claude (text, tool_use, tool_result)
- `status_update` — обновление status line
- `status_clear` — очистка status

**Механизмы:**
- **Merge**: последовательные content задачи объединяются (до 3800 chars)
- **Tool pairing**: tool_use message_id сохраняется → tool_result edit'ит его
- **Status conversion**: status message → первый content (edit вместо delete+send)
- **Flood control**: при RetryAfter > 10s — drop status, wait for content
- **Deduplication**: одинаковый status text не re-edit'ится

**Ключевые функции:**
- `enqueue_content_message()` — добавить контент в очередь
- `enqueue_status_update()` — добавить status update
- `_message_queue_worker()` — background worker per user
- `_merge_content_tasks()` — merge с drain/refill очереди
- `shutdown_workers()` — остановка всех workers
- `get_message_queue()` — получить очередь для user_id
- `get_or_create_queue()` — получить или создать очередь + worker
- `clear_status_msg_info()` — очистить status message info для topic
- `clear_tool_msg_ids_for_topic()` — очистить tool message IDs для topic

---

### `handlers/status_polling.py` — Polling статуса

**Что делает:** Background task, каждую секунду проверяет терминал для всех привязанных topic'ов.

**Интервалы:**
- `STATUS_POLL_INTERVAL = 1.0s` — status line polling
- `TOPIC_CHECK_INTERVAL = 60.0s` — проверка существования topic'ов

**Функции:**
- `status_poll_loop(bot)` — бесконечный цикл:
  - Каждые 60s: probe topic'ов через `unpin_all_forum_topic_messages` (silent no-op)
  - Каждую 1s: для каждого привязанного topic:
    - Cleanup stale bindings (window gone)
    - Detect interactive UI (permission prompts)
    - Enqueue status updates
- `update_status_message()` — poll terminal + check UI + enqueue status

---

### `handlers/interactive_ui.py` — Interactive UI

**Что делает:** Обработка интерактивных элементов Claude Code (AskUserQuestion, ExitPlanMode, Permission Prompt, etc.)

**Функции:**
- `handle_interactive_ui()` — capture terminal → send UI с inline keyboard
- `_build_interactive_keyboard()` — keyboard с ↑↓←→ Enter Esc Space Tab Refresh
- `set_interactive_mode()` / `clear_interactive_mode()` — track interactive state
- `get_interactive_window()` / `get_interactive_msg_id()` — lookup
- `clear_interactive_msg()` — delete message + clear state

**INTERACTIVE_TOOL_NAMES:** `{"AskUserQuestion", "ExitPlanMode"}` — триггерят через JSONL

---

### `handlers/directory_browser.py` — Directory Browser

**Что делает:** UI для выбора рабочей директории и resume сессии.

**UI компоненты:**
1. **Window Picker** — список незавязанных tmux окон
2. **Directory Browser** — навигация по файловой системе (6 dirs/page)
3. **Session Picker** — список существующих Claude сессий для resume

**Функции:**
- `build_window_picker(windows)` — UI для привязки к существующему окну
- `build_directory_browser(current_path, page)` — UI с пагинацией, вход в папки, select
- `build_session_picker(sessions)` — UI для resume (с relative time)
- `clear_browse_state()` / `clear_window_picker_state()` / `clear_session_picker_state()` — cleanup

---

### `handlers/response_builder.py` — Сборка ответов

**Что делает:** Форматирование и пагинация ответов для Telegram.

**Функция:**
- `build_response_parts(text, is_complete, content_type, role)` → list[str]
  - User messages: "👤 " prefix, truncate 3000
  - Thinking: "∴ Thinking…" prefix, truncate 500 chars
  - Text: no prefix, split to 3000 chars
  - Multi-part: `[1/N]` suffix
  - Expandable quotes: не split'ятся (atomic)

---

### `handlers/history.py` — История сообщений

**Что делает:** Отображение истории с пагинацией.

**Функция:**
- `send_history(target, window_id, offset, ...)` — полная или unread история
  - Поддержка byte range для unread
  - Timestamps как HH:MM
  - User messages с 👤, thinking с ∴
  - Split по 4096 chars → inline keyboard пагинация
  - Update user's read offset после просмотра

---

### `handlers/cleanup.py` — Очистка состояния

**Функция:**
- `clear_topic_state(user_id, thread_id, bot, user_data)` — очистка всего при удалении topic:
  - status_msg_info
  - tool_msg_ids
  - interactive_msgs + interactive_mode
  - pending thread state

---

## 8. State-файлы {#state-файлы}

Все в `~/.ccbot/` (или `$CCBOT_DIR/`):

| Файл | Формат | Кто пишет | Описание |
|---|---|---|---|
| `state.json` | JSON | SessionManager | thread bindings, window states, display names, read offsets, group_chat_ids |
| `session_map.json` | JSON | Hook (hook.py) | window_id → {session_id, cwd, window_name} |
| `monitor_state.json` | JSON | MonitorState | tracked sessions с byte offsets |

### state.json structure:
```json
{
  "window_states": {"@0": {"session_id": "uuid", "cwd": "/path"}},
  "user_window_offsets": {"12345": {"@0": 15234}},
  "thread_bindings": {"12345": {"42": "@0"}},
  "window_display_names": {"@0": "project-name"},
  "group_chat_ids": {"12345:42": -100123456789}
}
```

### session_map.json structure:
```json
{
  "ccbot:@0": {"session_id": "uuid", "cwd": "/path/to/project", "window_name": "project"}
}
```

---

## 9. Зависимости {#зависимости}

### Runtime
- `python-telegram-bot[rate-limiter]>=21.0` — Telegram Bot API + AIORateLimiter
- `python-dotenv>=1.0.0` — загрузка .env
- `httpx>=0.27.0` — HTTP клиент для OpenAI API
- `libtmux>=0.37.0` — tmux управление
- `Pillow>=10.0.0` — рендеринг скриншотов
- `aiofiles>=24.0.0` — async file I/O
- `telegramify-markdown>=0.5.0,<1.0.0` — MD → MarkdownV2

### Dev
- `pyright>=1.1.0` — type checking
- `pytest>=8.0` + `pytest-asyncio>=0.24.0` — testing
- `pytest-cov>=6.0` — coverage
- `ruff>=0.8.0` — linting + formatting

---

## 10. Тесты {#тесты}

### Unit tests (`tests/ccbot/`)
| Файл | Что тестирует |
|---|---|
| `test_config.py` | Config loading, env vars |
| `test_session.py` | SessionManager, bindings |
| `test_session_monitor.py` | Monitor polling, updates |
| `test_monitor_state.py` | State persistence |
| `test_terminal_parser.py` | UI detection, status line |
| `test_transcript_parser.py` | JSONL parsing, tool pairing |
| `test_telegram_sender.py` | Message splitting |
| `test_markdown_v2.py` | Markdown conversion |
| `test_hook.py` | Hook processing |
| `test_utils.py` | Utility functions |
| `test_transcribe.py` | Voice transcription |
| `test_forward_command.py` | Command forwarding |

### Handler tests (`tests/ccbot/handlers/`)
| Файл | Что тестирует |
|---|---|
| `test_interactive_ui.py` | Interactive UI handling |
| `test_status_polling.py` | Status polling |
| `test_response_builder.py` | Response building |

### Integration tests (`tests/integration/`)
| Файл | Что тестирует |
|---|---|
| `test_config_integration.py` | Real config loading |
| `test_monitor_state_integration.py` | Real state file I/O |

---

## 11. CI/CD {#cicd}

### `.github/workflows/check.yml`
- Lint: `ruff check`
- Format: `ruff format --check`
- Type check: `pyright`
- Tests: `pytest`

### `.github/workflows/claude.yml`
- Claude Code автоматизация

### `.github/workflows/claude-code-review.yml`
- Автоматическое code review через Claude

---

## 12. Фичи — полный список {#фичи}

### Реализованные фичи:

1. **1 Topic = 1 Window = 1 Session** — полная изоляция сессий
2. **Directory Browser** — навигация по FS для создания сессий
3. **Window Picker** — привязка к существующим свободным окнам
4. **Session Resume** — возобновление существующих Claude сессий через `--resume`
5. **Message Queue** — per-user FIFO с merge и rate limiting
6. **Tool Pairing** — tool_use → tool_result edit in-place
7. **Interactive UI** — AskUserQuestion, ExitPlanMode, Permission, Bash Approval, RestoreCheckpoint, Settings
8. **Status Line Polling** — real-time статус Claude Code в Telegram
9. **MarkdownV2** — полная конвертация с expandable blockquotes и fallback
10. **Expandable Quotes** — thinking и tool results в сворачиваемых цитатах
11. **Table Rendering** — MD таблицы → card-style KV pairs
12. **Message History** — пагинация с byte-range для unread
13. **Screenshots** — terminal → PNG с ANSI цветами и CJK support
14. **Voice Transcription** — голос → текст через OpenAI API
15. **Photo Forwarding** — фото → base64 image в Claude Code
16. **Hook Auto-Install** — `ccbot hook --install`
17. **Topic Lifecycle** — close/delete topic → kill window + cleanup
18. **Stale Binding Cleanup** — автоочистка мёртвых привязок
19. **Startup Re-Resolution** — восстановление window IDs после рестарта tmux
20. **Old Format Migration** — автомиграция с window names на window IDs
21. **Sensitive Var Scrubbing** — tokens не утекают в дочерние процессы
22. **Flood Control** — graceful handling при 429 от Telegram
23. **File Locking** — concurrent hook writes через fcntl
24. **Atomic JSON Writes** — crash-safe через temp+rename
25. **mtime Cache** — пропуск неизменённых файлов
26. **Byte Offset Incremental** — чтение только новых строк JSONL
27. **Corrupted Offset Recovery** — восстановление при mid-line offset
28. **File Truncation Detection** — автосброс offset при /clear
29. **Supergroup Forum Support** — group_chat_ids для topic routing
30. **Topic Name Sync** — при переименовании topic в Telegram автоматически переименовывается привязанный tmux window (через `topic_edited_handler`)
31. **CCBOT_SHOW_TOOL_CALLS** — скрытие tool calls
32. **CCBOT_SHOW_USER_MESSAGES** — скрытие user messages
33. **CCBOT_SHOW_HIDDEN_DIRS** — показ скрытых папок
34. **Custom Claude Projects Path** — поддержка Claude variants
35. **`!` Command Mode** — special handling для shell commands (1s delay)
36. **Edit Diff** — unified diff в tool_result для Edit tool
37. **Tool-specific Stats** — Read lines, Grep matches, Glob files, etc.
38. **Topic Existence Probing** — каждые 60s проверка что topic'ы ещё живы
39. **Multi-user Support** — concurrent users без интерференции
40. **`!` Command Bash Output Capture** — при отправке `!` shell-команд: 30s polling с 1s интервалом, вывод отправляется в Telegram
