# Архитектура CCBot

## Обзор системы

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Telegram Bot (bot.py)                       │
│  - Topic-based routing: 1 topic = 1 window = 1 session             │
│  - /history, /screenshot, /esc, /kill, /restart, /summary и др.    │
│  - Пересылка текста, фото, голоса, документов в Claude Code        │
│  - Создание сессий через directory browser в новых топиках         │
│  - tool_use -> tool_result: редактирование сообщения на месте      │
│  - Interactive UI: AskUserQuestion / ExitPlanMode / Permission      │
│  - Per-user message queue + worker (merge, rate limit)              │
│  - MarkdownV2 с автофолбэком на plain text                         │
├──────────────────────┬──────────────────────────────────────────────┤
│  markdown_v2.py      │  telegram_sender.py                         │
│  MD -> MarkdownV2    │  split_message (4096 limit)                 │
│  + expandable quotes │                                             │
├──────────────────────┴──────────────────────────────────────────────┤
│  terminal_parser.py                                                 │
│  - Детекция интерактивных UI (AskUserQuestion, ExitPlanMode и др.) │
│  - Парсинг status line (spinner + текст)                           │
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
           v                                  v
┌────────────────────────┐         ┌─────────────────────────┐
│  TranscriptParser      │         │  Tmux Windows           │
│  (transcript_parser.py)│         │  - Claude Code process  │
│  - Parse JSONL entries │         │  - One window per       │
│  - Pair tool_use <->   │         │    topic/session        │
│    tool_result         │         └────────────┬────────────┘
│  - Format expandable   │                      │
│    quotes for thinking │              SessionStart hook
│  - Extract history     │                      │
└────────────────────────┘                      v
                                    ┌────────────────────────┐
┌────────────────────────┐         │  Hook (hook.py)        │
│  SessionManager        │<────────│  - Receive hook stdin  │
│  (session.py)          │  reads  │  - Write session_map   │
│  - Window <-> Session  │  map    │    .json               │
│    resolution          │         └────────────────────────┘
│  - Thread bindings     │
│    (topic -> window)   │         ┌────────────────────────┐
│  - Message history     │────────>│  Claude Sessions       │
│    retrieval           │  reads  │  ~/.claude/projects/   │
└────────────────────────┘  JSONL  │  - sessions-index      │
                                   │  - *.jsonl files       │
┌────────────────────────┐         └────────────────────────┘
│  MonitorState          │
│  (monitor_state.py)    │         ┌────────────────────────┐
│  - Track byte offset   │         │  WS Bridge             │
│  - Prevent duplicates  │         │  (ws_bridge.py)        │
│    after restart       │         │  - WebSocket server    │
└────────────────────────┘         │  - 26 typed messages   │
                                   │  - Auth + rate limit   │
                                   │  - Terminal diff       │
                                   │    streaming           │
                                   └────────────────────────┘
```

## Модули

### Ядро

#### `main.py`

Точка входа CLI. Три режима работы:

- `ccbot hook` -- делегирует в `hook.hook_main()` для обработки SessionStart хука
- `ccbot web` -- запускает WS bridge без Telegram-бота
- По умолчанию -- запуск Telegram-бота (с опциональным `--with-web`)

Настраивает ротируемое логирование (1 МБ, 3 бэкапа, `chmod 600`).

Зависимости: `config`, `tmux_manager`, `bot`, `ws_bridge` (опционально).

#### `config.py`

Singleton конфигурации. Загружает переменные окружения из `.env` файлов с приоритетом: локальный `.env` > `~/.ccbot/.env`.

Ключевые функции:

- Валидация обязательных переменных при старте
- Парсинг `ALLOWED_USERS` в множество int
- Резолв `CCBOT_ALLOWED_ROOTS` с проверкой существования директорий
- Скрабинг 6 чувствительных переменных из `os.environ` после загрузки (`TELEGRAM_BOT_TOKEN`, `ALLOWED_USERS`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `DEEPGRAM_API_KEY`, `CCBOT_WS_TOKEN`)

Зависимости: `python-dotenv`, `utils`.

#### `bot.py`

Главный UI-слой. Содержит все Telegram-хэндлеры, маршрутизацию callback-ов, управление жизненным циклом. Около 3000 строк.

Ключевые подсистемы:

- **Command handlers**: 12 команд (`/start`, `/help`, `/history`, `/screenshot`, `/esc`, `/unbind`, `/kill`, `/restart`, `/usage`, `/health`, `/summary`, `/sessions`)
- **Content handlers**: текст, фото, голос, документы, правки сообщений, реакции
- **Background tasks**: очистка старых файлов (каждые 6 часов), input batching (debounce 1.5 секунды), auto-naming топиков
- **Callback handler**: маршрутизация 20+ типов inline-кнопок (пагинация истории, браузер директорий, пикер окон/сессий, скриншот, interactive UI)
- **Lifecycle**: startup-диагностика, shutdown с уведомлением пользователей, глобальный error handler с алертами разработчику

Зависимости: все модули проекта.

#### `session.py`

Центральный хаб состояния. Класс `SessionManager` управляет:

- `thread_bindings` -- маппинг `user_id -> {thread_id -> window_id}`
- `window_display_names` -- `window_id -> window_name` (для отображения)
- `window_states` -- `window_id -> WindowState(session_id, cwd, window_name)`
- `group_chat_ids` -- маппинг для supergroup routing

Ключевые операции:

- `resolve_stale_ids()` -- ре-маппинг window ID после перезапуска tmux
- `resolve_session_for_window()` -- window_id -> `ClaudeSession` с путем к JSONL
- `list_sessions_for_directory()` -- список существующих сессий для resume picker
- `send_to_window()` -- отправка текста в tmux через `TmuxManager`

Персистенция: `state.json` (атомарная запись через `atomic_write_json`).

Зависимости: `tmux_manager`, `utils`, `config`.

#### `hook.py`

Обработчик SessionStart хука Claude Code. При вызове:

1. Читает JSON из stdin (session_id, cwd, window_id)
2. Валидирует session_id как UUID
3. Записывает в `session_map.json` с file locking (`fcntl.flock`)

Также содержит `--install` для автоустановки хука в `~/.claude/settings.json` и `_update_hook_path()` для обновления пути при его изменении.

Зависимости: `utils`.

### Мониторинг

#### `session_monitor.py`

Polling loop: каждые 2-3 секунды читает JSONL-файлы сессий.

Ключевой процесс:

1. Загрузка `session_map.json` для определения активных сессий
2. Проверка mtime файлов (кэш в памяти, пропуск неизменившихся)
3. Инкрементальное чтение по byte offset
4. Парсинг новых строк через `TranscriptParser`
5. Отслеживание `pending_tools` между циклами polling (tool_use без tool_result)
6. Доставка `NewMessage` через список callback-ов (Telegram-бот + WS bridge)

Дополнительно: детекция Write-инструмента для автоотправки файлов, формирование прогресс-статуса с описанием текущего инструмента.

Зависимости: `transcript_parser`, `session`, `monitor_state`, `config`.

#### `monitor_state.py`

Персистенция byte offset для каждой отслеживаемой сессии. Класс `MonitorState` с dirty flag оптимизацией -- запись в `monitor_state.json` только при изменениях.

Данные: `TrackedSession(session_id, file_path, last_byte_offset)`.

Зависимости: `utils`.

#### `terminal_parser.py`

Парсинг текста терминала Claude Code:

- 8 паттернов интерактивных UI (`ExitPlanMode`, `AskUserQuestion` x2, `PermissionPrompt` x2, `BashApproval`, `RestoreCheckpoint`, `Settings`)
- Извлечение status line (spinner + рабочий текст)
- Удаление chrome (prompt, status bar)
- Извлечение вывода bash-команд
- Парсинг `/usage` модального окна

Зависимости: нет (standalone).

#### `transcript_parser.py`

Парсер JSONL-файлов сессий Claude Code. Обрабатывает:

- `text` и `thinking` контент
- `tool_use` -- форматирование для 15+ типов инструментов (Read, Write, Edit, Bash, Grep, Glob, Task, WebFetch, WebSearch, MCP и др.)
- `tool_result` -- текст и base64-изображения
- `local_command` -- активация скиллов

Ключевое: `parse_entries()` используется и монитором (реал-тайм), и историей, с общей логикой pairing tool_use <-> tool_result.

Зависимости: нет (standalone).

### Отправка сообщений

#### `handlers/message_queue.py`

Per-user очередь сообщений с фоновым worker:

- FIFO-порядок с автоматическим merge последовательных content-сообщений (до 3800 символов)
- `tool_use` разрывает цепочку merge и отправляется отдельно (message_id сохраняется)
- `tool_result` редактирует исходное сообщение `tool_use` на месте
- Конвертация status-сообщения в первое content-сообщение (уменьшает количество сообщений)
- Flood control: ожидание при RetryAfter, дроп status-ов после 10 секунд бана

Зависимости: `markdown_v2`, `message_sender`, `response_builder`, `session`.

#### `handlers/message_sender.py`

Safe-обертки для отправки сообщений:

- `safe_reply()`, `safe_edit()`, `safe_send()` -- MarkdownV2 с двойным фолбэком на plain text
- `send_photo()` -- одиночное фото или media group
- `send_with_fallback()` -- базовая send с retry-логикой

Зависимости: `markdown_v2`.

#### `handlers/response_builder.py`

Построение пагинированных ответов:

- Разбиение на части с суффиксом `[1/N]`
- Thinking-контент обрезается до 500 символов в expandable quote
- Консервативный лимит 3000 символов (запас для MarkdownV2 expansion)

Зависимости: нет.

#### `telegram_sender.py`

Разбиение длинных сообщений по лимиту 4096 символов с корректным закрытием/открытием fenced code blocks при сплите.

Зависимости: нет.

#### `markdown_v2.py`

Конвертация Markdown в Telegram MarkdownV2:

- Markdown-таблицы в card-style формат
- Expandable blockquotes (`>...||`)
- Обертка через `telegramify-markdown`

Зависимости: `telegramify-markdown`.

### UI и обработчики

#### `handlers/interactive_ui.py`

Обработка интерактивных запросов Claude Code:

- AskUserQuestion, ExitPlanMode, PermissionPrompt
- Клавиатура навигации: Space/Up/Tab, Left/Down/Right, Esc/Refresh/Enter
- Capture терминала и отправка как отформатированный текст

Зависимости: `terminal_parser`, `tmux_manager`, `message_sender`.

#### `handlers/directory_browser.py`

UI навигации по файловой системе при создании новых сессий:

- Пагинированный браузер директорий (6 на страницу)
- Проверка `allowed_roots` при навигации и при подтверждении
- Session picker для возобновления существующих сессий
- Window picker для привязки к свободным tmux-окнам

Зависимости: `config`, `session`.

#### `handlers/status_polling.py`

Фоновый polling (интервал 3 секунды):

- Опрос status line терминала для всех привязанных окон
- Детекция мертвых сессий + автоперезапуск (--resume, max 2 попытки, cooldown 60 секунд)
- Проверка существования топиков (каждые 60 секунд через API)
- Очистка stale bindings (окно удалено извне)
- Idle reminder (по умолчанию 120 секунд)
- Детекция интерактивных UI

Зависимости: `terminal_parser`, `tmux_manager`, `session`, `interactive_ui`, `message_queue`.

#### `handlers/history.py`

Отображение истории сообщений с inline-кнопками для пагинации. Использует `TranscriptParser` и `SessionManager.get_recent_messages()`.

Зависимости: `session`, `transcript_parser`, `message_sender`.

#### `handlers/cleanup.py`

Централизованная очистка состояния топика при удалении: status_msg_info, tool_msg_ids, interactive_msgs, pending state.

Зависимости: `message_queue`, `interactive_ui`.

#### `handlers/callback_data.py`

16 констант для callback data inline-кнопок (префиксы `CB_HISTORY_*`, `CB_DIR_*`, `CB_WIN_*`, `CB_SCREENSHOT_*`, `CB_ASK_*`, `CB_SESSION_*`, `CB_KEYS_PREFIX`).

Зависимости: нет.

### Внешние интеграции

#### `tmux_manager.py`

Async-обертка над libtmux:

- CRUD для tmux-окон (list, find by name/ID, create, kill, rename)
- `send_keys()` -- literal-режим с задержками для Claude Code TUI
- `capture_pane()` -- захват текста с/без ANSI
- `is_claude_running()` -- `pgrep -P <pane_pid>`
- Скрабинг чувствительных переменных из tmux session environment
- Фильтрация null-байтов и непечатных символов в send_keys

Зависимости: `libtmux`, `config`.

#### `screenshot.py`

Рендеринг текста терминала в PNG:

- Парсинг ANSI escape codes (SGR, 256 цветов)
- Font fallback chain: JetBrains Mono -> Noto Sans CJK -> Symbola
- Шрифты загружаются из `src/ccbot/fonts/`

Зависимости: `Pillow`.

#### `transcribe.py`

Транскрипция голосовых сообщений через Deepgram Nova-3 API:

- Вход: OGG-байты, выход: текст
- Язык: hardcoded `ru`
- Lazy singleton `httpx.AsyncClient`

Зависимости: `httpx`.

### WebSocket Bridge

#### `ws_bridge.py`

WS-сервер для веб-фронтенда (664 строки):

- Аутентификация через token + `hmac.compare_digest`; localhost bypass без токена
- Маршрутизация: create/resume session, browse directory, send message/key, upload file
- Автоматическое подключение к `SessionMonitor` как дополнительный callback
- Rate limiting: 60 msg/min, max 20 соединений, max message 1 МБ, max file 50 МБ
- Auth timeout 30 секунд для неаутентифицированных соединений

Зависимости: `websockets`, `session`, `tmux_manager`, `config`, `ws_protocol`, `terminal_stream`.

#### `ws_protocol.py`

26 типизированных dataclass-ов для WS-протокола. Парсинг и сериализация клиентских и серверных сообщений.

Зависимости: нет.

#### `terminal_stream.py`

Периодический захват терминала с diff-доставкой. Отправляет клиенту только изменившиеся строки.

Зависимости: `tmux_manager`.

### Утилиты

#### `utils.py`

- `ccbot_dir()` -- путь к конфиг-директории (`~/.ccbot` или `$CCBOT_DIR`)
- `atomic_write_json()` -- crash-safe запись через temp + `os.fsync` + `os.replace`
- `read_cwd_from_jsonl()` -- извлечение cwd из первой записи JSONL
- `write_shutdown_marker()` / `read_and_clear_shutdown_marker()` -- маркер чистого shutdown

Зависимости: нет.

## Потоки данных

### Outbound: Claude Code -> Telegram

```
Claude Code записывает в JSONL-файл сессии
    |
    v
SessionMonitor (polling каждые 2-3 секунды)
    |-- проверка mtime файла (кэш в памяти)
    |-- инкрементальное чтение по byte offset
    |-- парсинг через TranscriptParser
    |
    v
NewMessage(session_id, text, content_type, ...)
    |
    v
handle_new_message() в bot.py
    |-- резолв session_id -> (user_id, thread_id) через thread_bindings
    |-- маршрутизация по content_type:
    |   - "content" / "tool_use" / "tool_result" -> enqueue_content_message()
    |   - "status" -> enqueue_status_update()
    |   - "file" -> отправка документа в топик
    |   - "interactive" -> handle_interactive_ui()
    |
    v
Message Queue Worker (per-user)
    |-- merge последовательных content-сообщений (до 3800 символов)
    |-- tool_result -> edit исходного tool_use сообщения
    |-- MarkdownV2 конвертация + split по 4096
    |-- flood control (ожидание при RetryAfter)
    |
    v
Telegram API (safe_reply / safe_edit / safe_send)
```

### Inbound: Telegram -> Claude Code

```
Пользователь отправляет сообщение в топик
    |
    v
text_handler() / photo_handler() / voice_handler() / document_handler()
    |-- проверка is_user_allowed()
    |-- проверка rate limit (30 msg / 60 сек)
    |-- резолв thread_id -> window_id через thread_bindings
    |
    |-- [если топик не привязан]
    |   |-- directory_browser -> выбор директории
    |   |-- session_picker (если есть сессии) или create_window
    |   |-- bind_thread() + отправка pending сообщения
    |
    |-- [если топик привязан]
    |   |-- debounce: _enqueue_batched_input (1.5 секунды)
    |   |-- _flush_input_buffer -> session_manager.send_to_window()
    |
    v
TmuxManager.send_keys(window_id, text, literal=True)
    |-- фильтрация null-байтов и непечатных символов
    |-- libtmux: pane.send_keys(chars, literal=True)
    |
    v
Claude Code читает ввод из терминала
```

### WebSocket Bridge

```
Веб-клиент
    |
    v
ws_bridge.py (WebSocket server, порт 8765)
    |-- аутентификация (token / localhost bypass)
    |-- маршрутизация по типу сообщения:
    |   - create_session -> TmuxManager.create_window()
    |   - resume_session -> TmuxManager.create_window(resume_session_id)
    |   - send_message -> SessionManager.send_to_window()
    |   - send_key -> TmuxManager.send_keys() (whitelist клавиш)
    |   - browse_directory -> листинг директории
    |   - upload_file -> сохранение в ~/.ccbot/documents/
    |
    v
SessionMonitor -> bridge.on_new_message() callback
    |
    v
WS-клиенту:
    - WsAssistantMessage (текст, thinking)
    - WsStatusUpdate (прогресс)
    - WsFileMessage (файл)
    - WsInteractiveUI (запрос от Claude)
    - WsTerminalUpdate (diff терминала от TerminalStream)
```

## State management

### `state.json`

Расположение: `~/.ccbot/state.json`.

Содержит:

| Поле | Тип | Назначение |
|------|-----|-----------|
| `thread_bindings` | `{user_id: {thread_id: window_id}}` | Привязки топиков к tmux-окнам |
| `window_display_names` | `{window_id: window_name}` | Имена окон для отображения в UI |
| `window_states` | `{window_id: {session_id, cwd, window_name}}` | Состояние каждого окна |
| `group_chat_ids` | `{user_id: {thread_id: chat_id}}` | Supergroup routing |
| `read_offsets` | `{user_id: {window_id: byte_offset}}` | Что пользователь уже прочитал |

Жизненный цикл: загружается при старте, обновляется при каждом изменении привязок/состояний, записывается атомарно через `atomic_write_json`.

### `session_map.json`

Расположение: `~/.ccbot/session_map.json`.

Формат ключей: `"tmux_session:window_id"` (например `"ccbot:@0"`).

```json
{
  "ccbot:@0": {
    "session_id": "uuid-xxx",
    "cwd": "/path/to/project",
    "window_name": "project"
  }
}
```

Жизненный цикл: записывается хуком SessionStart при каждом старте/рестарте сессии Claude Code. Читается монитором при каждом цикле polling. File locking через `fcntl.flock`.

### `monitor_state.json`

Расположение: `~/.ccbot/monitor_state.json`.

Содержит byte offset для каждого отслеживаемого JSONL-файла. Предотвращает повторную доставку сообщений после перезапуска бота. Записывается условно (dirty flag).

### In-memory state (не персистируется)

| Структура | Модуль | Назначение |
|-----------|--------|-----------|
| `_msg_thread_map` | bot.py | message_id -> (thread_id, window_id) для реакций. Лимит 10 000 записей |
| `_interactive_mode` | interactive_ui.py | Текущие окна в интерактивном режиме |
| `_interactive_msgs` | interactive_ui.py | ID сообщений интерактивных UI |
| `_status_msg_info` | message_queue.py | Текущее status-сообщение на пользователя |
| `_restart_attempts` | status_polling.py | Счетчики автоперезапуска по окнам |
| mtime cache | session_monitor.py | Кэш времени модификации JSONL-файлов |
| pending_tools | session_monitor.py | tool_use без соответствующего tool_result |

## Принципы проектирования

### Topic-centric архитектура

Каждый топик Telegram-форума -- самостоятельная рабочая среда. Нет централизованного списка сессий; топики и есть список сессий. Создал топик -- выбрал директорию -- работаешь. Закрытие/удаление топика автоматически завершает tmux-окно и очищает привязки.

### Window ID как внутренний ключ

Все внутреннее состояние привязано к tmux window ID (`@0`, `@12`), а не к имени окна. Window ID уникальны в рамках tmux-сервера. Имена хранятся отдельно в `window_display_names` для отображения. Одна директория может иметь несколько окон.

При перезапуске tmux window ID сбрасываются. `resolve_stale_ids()` при старте бота сопоставляет сохраненные display names с живыми окнами для восстановления маппинга.

### Hook-based session tracking

Бот не сканирует файловую систему в поисках сессий. Отслеживаются только сессии, зарегистрированные через хук в `session_map.json`. Это дает точное соответствие window <-> session и минимизирует дисковый IO.

### Без truncation на уровне парсинга

Контент никогда не обрезается при парсинге. Полная длина tool_use summaries, tool_result текста, user/assistant сообщений сохраняется. Разбиение на части происходит исключительно на уровне отправки (`split_message` для 4096-символьного лимита, `build_response_parts` для пагинации).

### Per-user очередь с merge

Каждый пользователь имеет собственную очередь и worker. Это обеспечивает:

- FIFO-порядок сообщений
- Автоматическое склеивание последовательных коротких сообщений (до 3800 символов)
- Изоляцию между пользователями (flood одного не блокирует другого)
- Корректный pairing tool_use / tool_result (tool_result редактирует исходное сообщение на месте)

### MarkdownV2 с деградацией

Все сообщения проходят через `safe_reply` / `safe_edit` / `safe_send`, которые:

1. Конвертируют Markdown в MarkdownV2 через `telegramify-markdown`
2. При ошибке парсинга -- фолбэк на plain text
3. При повторной ошибке -- отправка без форматирования

Это гарантирует доставку сообщения при любом содержимом.
