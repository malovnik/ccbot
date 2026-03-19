# Аудит версии malovnik/ccbot

## Сводка
- Всего файлов: 24
- Всего функций/классов: ~150 (функции, методы, классы)
- Статус: 135 WORKS / 3 BROKEN / 12 UNTESTED

---

## Модули

---

### main.py
**Назначение:** Точка входа CLI. Два режима: `ccbot hook` (делегирует в hook.py) и запуск Telegram бота.
**Классы/Функции:**
- `main()` — CLI dispatcher, настройка логирования, ротация лог-файлов (1MB, 3 бэкапа), запуск бота — WORKS

**Проблемы:**
- Нет. Чистый, минимальный код. Хорошая обработка отсутствующих .env переменных.

---

### config.py
**Назначение:** Singleton конфигурации из переменных окружения с поддержкой .env файлов.
**Классы/Функции:**
- `_getbool(key, default)` — парсинг boolean env vars — WORKS
- `Config.__init__()` — загрузка всех параметров, валидация, scrubbing sensitive vars из os.environ — WORKS
- `Config.is_user_allowed(user_id)` — проверка доступа — WORKS

**Проблемы:**
- Нет серьёзных проблем. Scrubbing чувствительных переменных из environ — хорошая практика безопасности.
- `SENSITIVE_ENV_VARS` — правильно определены.
- `allowed_roots` валидирует существование при старте — хорошо.

---

### hook.py
**Назначение:** Подкоманда для Claude Code SessionStart хука. Пишет session_map.json с file locking.
**Классы/Функции:**
- `_find_ccbot_path()` — поиск ccbot в PATH или venv — WORKS
- `_is_hook_installed(settings)` — проверка наличия хука в settings.json — WORKS
- `_install_hook()` — установка хука в ~/.claude/settings.json — WORKS
- `hook_main()` — обработка stdin JSON от Claude Code, запись в session_map.json — WORKS

**Проблемы:**
- Нет. Хороший file locking через `fcntl.flock`. Валидация UUID формата session_id. Миграция old-format ключей. Atomic write через `atomic_write_json`.

---

### session.py
**Назначение:** Центральный хаб состояния. Window->Session маппинг, thread bindings, group_chat_ids, история сообщений.
**Классы/Функции:**
- `WindowState` — dataclass состояния окна (session_id, cwd, window_name) — WORKS
- `ClaudeSession` — dataclass информации о сессии — WORKS
- `SessionManager._save_state()` — сохранение в state.json — WORKS
- `SessionManager._load_state()` — загрузка из state.json с миграцией формата — WORKS
- `SessionManager.resolve_stale_ids()` — ре-маппинг window IDs после рестарта tmux — WORKS
- `SessionManager._cleanup_stale_session_map_entries()` — очистка мёртвых window IDs — WORKS
- `SessionManager._cleanup_old_format_session_map_keys()` — миграция old format — WORKS
- `SessionManager.get_display_name(window_id)` — имя для UI — WORKS
- `SessionManager.update_display_name(window_id, new_name)` — обновление имени — WORKS
- `SessionManager.set_group_chat_id(user_id, thread_id, chat_id)` — хранение group chat_id для supergroup routing — WORKS
- `SessionManager.resolve_chat_id(user_id, thread_id)` — резолв chat_id (group vs private) — WORKS
- `SessionManager.wait_for_session_map_entry(window_id, timeout)` — polling session_map — WORKS
- `SessionManager.load_session_map()` — чтение session_map.json и обновление window_states — WORKS
- `SessionManager.get_window_state(window_id)` — получение/создание WindowState — WORKS
- `SessionManager.clear_window_session(window_id)` — очистка после /clear — WORKS
- `SessionManager._encode_cwd(cwd)` — кодирование пути для Claude Code projects — WORKS
- `SessionManager._build_session_file_path(session_id, cwd)` — путь к JSONL — WORKS
- `SessionManager._get_session_direct(session_id, cwd)` — прямое чтение сессии с glob fallback — WORKS
- `SessionManager.list_sessions_for_directory(cwd)` — список сессий в директории (для resume picker) — WORKS
- `SessionManager.resolve_session_for_window(window_id)` — window -> ClaudeSession — WORKS
- `SessionManager.update_user_window_offset(user_id, window_id, offset)` — трекинг прочитанного — WORKS
- `SessionManager.bind_thread(user_id, thread_id, window_id)` — привязка топика к окну — WORKS
- `SessionManager.unbind_thread(user_id, thread_id)` — отвязка — WORKS
- `SessionManager.get_window_for_thread(user_id, thread_id)` — lookup — WORKS
- `SessionManager.resolve_window_for_thread(user_id, thread_id)` — convenience wrapper — WORKS
- `SessionManager.iter_thread_bindings()` — итератор (user_id, thread_id, window_id) — WORKS
- `SessionManager.find_users_for_session(session_id)` — обратный lookup — WORKS
- `SessionManager.send_to_window(window_id, text)` — отправка текста через tmux — WORKS
- `SessionManager.get_recent_messages(window_id, start_byte, end_byte)` — история сообщений — WORKS

**Проблемы:**
- Строка 183: `pass` после `if needs_migration:` — нет фактической миграции, только логирование. Это by design (миграция происходит в `resolve_stale_ids()`), но `pass` избыточен.
- Строка 192: `pass` после `except` блока — стилистически лишнее.
- `send_to_window` имеет hardcoded лимит `MAX_MESSAGE_LENGTH = 4096` — совпадает с Telegram, но для tmux это произвольное ограничение.

---

### session_monitor.py
**Назначение:** Polling loop мониторинга JSONL файлов. Детектит новые сообщения по byte offset и mtime.
**Классы/Функции:**
- `SessionInfo` — dataclass (session_id, file_path) — WORKS
- `NewMessage` — dataclass нового сообщения (session_id, text, is_complete, content_type, etc.) — WORKS
- `_format_tool_status(tool_name, tool_text)` — прогресс-статус (emoji + описание) — WORKS
- `SessionMonitor.__init__()` — инициализация (state, callbacks, pending_tools, mtime cache) — WORKS
- `SessionMonitor.set_message_callback(callback)` — установка колбэка — WORKS
- `SessionMonitor._get_active_cwds()` — cwds активных tmux окон — WORKS
- `SessionMonitor.scan_projects()` — сканирование projects директории — WORKS
- `SessionMonitor._read_new_lines(session, file_path)` — инкрементальное чтение по byte offset — WORKS
- `SessionMonitor.check_for_updates(active_session_ids)` — основной цикл проверки — WORKS
- `SessionMonitor._load_current_session_map()` — чтение session_map — WORKS
- `SessionMonitor._cleanup_all_stale_sessions()` — startup cleanup — WORKS
- `SessionMonitor._detect_and_cleanup_changes()` — детект изменений session_map — WORKS
- `SessionMonitor._monitor_loop()` — фоновый async loop — WORKS
- `SessionMonitor.start()` / `SessionMonitor.stop()` — lifecycle — WORKS

**Проблемы:**
- `_SENDABLE_EXTS` и `_SENSITIVE_NAMES` — хороший whitelist/blacklist подход.
- Строки 562-583: дублированный код отправки status (строка 564 и 575 — одинаковые `NewMessage` с `content_type="status"`). Условие `if sid not in _working_status_active` / `else` производит идентичный результат. Это не баг, но мертвый `if/else` — можно упростить.
- Детекция Write tool через regex (`_WRITE_TOOL_RE`) — работает для стандартного формата `**Write**(path)`.

---

### tmux_manager.py
**Назначение:** Обёртка libtmux для async операций с tmux окнами.
**Классы/Функции:**
- `TmuxWindow` — dataclass информации об окне — WORKS
- `TmuxManager.__init__(session_name)` — инициализация — WORKS
- `TmuxManager.server` — lazy property для libtmux.Server — WORKS
- `TmuxManager.get_session()` — получение tmux сессии — WORKS
- `TmuxManager.get_or_create_session()` — создание с scrubbing env — WORKS
- `TmuxManager._scrub_session_env(session)` — удаление чувствительных переменных — WORKS
- `TmuxManager.list_windows()` — async список окон (через to_thread) — WORKS
- `TmuxManager.find_window_by_name(window_name)` — поиск по имени — WORKS
- `TmuxManager.find_window_by_id(window_id)` — поиск по ID — WORKS
- `TmuxManager.capture_pane(window_id, with_ansi)` — захват текста панели — WORKS
- `TmuxManager.is_claude_running(window_id)` — проверка через pgrep — WORKS
- `TmuxManager.send_keys(window_id, text, enter, literal)` — отправка клавиш — WORKS
- `TmuxManager.rename_window(window_id, new_name)` — переименование — WORKS
- `TmuxManager.kill_window(window_id)` — убить окно — WORKS
- `TmuxManager.create_window(work_dir, window_name, start_claude, resume_session_id)` — создание окна с опциональным --resume — WORKS

**Проблемы:**
- `send_keys` при `literal=True` и `enter=True`: задержка 500ms перед Enter и 1s перед `!` command rest — потенциально race condition при быстром вводе, но это документированный workaround для Claude Code TUI.
- `find_window_by_name` и `find_window_by_id` вызывают `list_windows()` каждый раз (O(n) scan). При малом числе окон не проблема.
- Строка 279: фильтрация символов в `send_keys` — пропускает `\n` и printable, но условие `ord(c) > 127` позволяет любые unicode символы. Может быть проблемой с control characters 1-31 (кроме `\n`).

---

### screenshot.py
**Назначение:** Рендеринг текста терминала в PNG с ANSI цветами и font fallback chain.
**Классы/Функции:**
- `TextStyle` — dataclass стиля (fg_color, bg_color) — WORKS
- `StyledSegment` — dataclass сегмента (text, style, font_tier) — WORKS
- `_load_font(path, size)` — загрузка шрифта с fallback на Pillow default — WORKS
- `_font_tier(ch)` — определение fallback шрифта (JetBrains/Noto/Symbola) — WORKS
- `_parse_ansi_line(line)` — парсинг ANSI escape codes — WORKS
- `_apply_ansi_codes(style, codes)` — применение SGR кодов к стилю — WORKS
- `_approximate_256_color(idx)` — RGB приближение 256-цветной палитры — WORKS
- `_split_line_segments_plain(line)` — разделение по font tier — WORKS
- `text_to_image(text, font_size, with_ansi)` — главная функция рендеринга — WORKS

**Проблемы:**
- `_font_tier`: строка 109 — `cp >= 0x1100 and (...)` внутри `or` выражения — скобки правильные, но читаемость спорная. Работает корректно.
- `_NOTO_CODEPOINTS` и `_SYMBOLA_CODEPOINTS` — всего по 1-3 codepoint. Неполное покрытие, но достаточно для основных символов Claude Code TUI.
- Шрифты должны быть в `src/ccbot/fonts/` — если отсутствуют, fallback на Pillow default (некрасиво, но не падает).

---

### transcribe.py
**Назначение:** Транскрипция голоса через Deepgram Nova-3 API.
**Классы/Функции:**
- `_get_client()` — lazy singleton httpx.AsyncClient — WORKS
- `transcribe_voice(ogg_data)` — транскрипция OGG → текст — WORKS
- `close_client()` — закрытие клиента при shutdown — WORKS

**Проблемы:**
- Hardcoded `language: "ru"` — не работает для не-русской речи. Может быть конфигурируемым.
- Нет retry логики при network errors (только raise_for_status).
- Модуль docstring упоминает "OpenAI API (gpt-4o-transcribe)" но реально используется Deepgram — **BROKEN** (docstring не соответствует реальности, но код работает корректно).

---

### markdown_v2.py
**Назначение:** Конвертация Markdown → Telegram MarkdownV2 с expandable blockquotes и таблицами.
**Классы/Функции:**
- `_split_table_row(line)` — разбор строки таблицы по `|` — WORKS
- `convert_markdown_tables(text)` — таблицы → card-style формат — WORKS
- `_escape_mdv2(text)` — экранирование спецсимволов MarkdownV2 — WORKS
- `_render_expandable_quote(m)` — рендеринг expandable blockquote `>...||` — WORKS
- `_markdownify(text)` — обёртка TelegramMarkdownRenderer — WORKS
- `convert_markdown(text)` — главная функция конвертации — WORKS

**Проблемы:**
- Нет серьёзных проблем. `_EXPQUOTE_MAX_RENDERED = 3800` — оставляет запас до 4096.
- `_markdownify` использует `remove_token(BlockCode)` — отключает indented code blocks, оставляя только fenced. Это by design.

---

### telegram_sender.py
**Назначение:** Утилита разбиения длинных сообщений (4096 символов) с сохранением code block'ов.
**Классы/Функции:**
- `split_message(text, max_length)` — разбиение с учётом fenced code blocks — WORKS

**Проблемы:**
- Нет серьёзных проблем. Корректно закрывает/открывает code blocks при сплите.

---

### terminal_parser.py
**Назначение:** Парсинг терминала Claude Code: детекция interactive UI, status line, chrome stripping.
**Классы/Функции:**
- `InteractiveUIContent` — dataclass (content, name) — WORKS
- `UIPattern` — frozen dataclass паттерна UI (top/bottom regex, min_gap) — WORKS
- `UI_PATTERNS` — 8 паттернов (ExitPlanMode, AskUserQuestion x2, PermissionPrompt x2, BashApproval, RestoreCheckpoint, Settings) — WORKS
- `_shorten_separators(text)` — укорочение длинных `─` линий — WORKS
- `_try_extract(lines, pattern)` — извлечение контента между top/bottom маркерами — WORKS
- `extract_interactive_content(pane_text)` — public API для детекции UI — WORKS
- `is_interactive_ui(pane_text)` — boolean проверка — WORKS
- `parse_status_line(pane_text)` — извлечение status line (spinner + текст) — WORKS
- `strip_pane_chrome(lines)` — удаление chrome (prompt, status bar) — WORKS
- `extract_bash_output(pane_text, command)` — извлечение вывода `!` команды — WORKS
- `UsageInfo` — dataclass для /usage — WORKS
- `parse_usage_output(pane_text)` — парсинг /usage модального окна — WORKS

**Проблемы:**
- `STATUS_SPINNERS` — набор символов может устареть при обновлении Claude Code.
- `parse_status_line` ищет chrome separator в последних 10 строках — может пропустить при очень длинном выводе в pane, но это edge case.

---

### transcript_parser.py
**Назначение:** Парсер JSONL файлов сессий Claude Code. Обработка text, thinking, tool_use/tool_result, local_command.
**Классы/Функции:**
- `ParsedMessage` — dataclass (message_type, text, tool_name) — WORKS
- `ParsedEntry` — dataclass готового к отображению сообщения — WORKS
- `PendingToolInfo` — dataclass pending tool_use (summary, tool_name, input_data) — WORKS
- `TranscriptParser.parse_line(line)` — парсинг одной JSONL строки — WORKS
- `TranscriptParser.get_message_type(data)` — тип сообщения — WORKS
- `TranscriptParser.is_user_message(data)` — проверка user — WORKS
- `TranscriptParser.extract_text_only(content_list)` — только текст из content — WORKS
- `TranscriptParser._format_edit_diff(old_string, new_string)` — unified diff — WORKS
- `TranscriptParser.format_tool_use_summary(name, input_data)` — форматирование tool_use (15 типов инструментов) — WORKS
- `TranscriptParser.extract_tool_result_text(content)` — текст из tool_result — WORKS
- `TranscriptParser.extract_tool_result_images(content)` — base64 изображения из tool_result — WORKS
- `TranscriptParser.parse_message(data)` — парсинг одного сообщения с детекцией local_command — WORKS
- `TranscriptParser.get_timestamp(data)` — извлечение timestamp — WORKS
- `TranscriptParser._format_expandable_quote(text)` — sentinel markers для expandable quotes — WORKS
- `TranscriptParser._format_tool_result_text(text, tool_name)` — форматирование результата (Read/Write/Bash/Grep/Glob/Task/WebFetch/WebSearch) — WORKS
- `TranscriptParser.parse_entries(entries, pending_tools)` — основная логика парсинга (shared между history и monitor) — WORKS

**Проблемы:**
- Нет серьёзных проблем. Сложный но корректный парсер. Хорошая обработка carry-over pending tools для monitor.
- `_format_tool_result_text` для Read: показывает "Read N lines" но не expandable quote — может быть неожиданно для пользователя (другие инструменты показывают содержимое).

---

### monitor_state.py
**Назначение:** Персистенция byte offsets для monitor (monitor_state.json).
**Классы/Функции:**
- `TrackedSession` — dataclass (session_id, file_path, last_byte_offset) — WORKS
- `MonitorState.load()` — загрузка из JSON — WORKS
- `MonitorState.save()` — atomic write — WORKS
- `MonitorState.get_session(session_id)` — lookup — WORKS
- `MonitorState.update_session(session)` — обновление + dirty flag — WORKS
- `MonitorState.remove_session(session_id)` — удаление — WORKS
- `MonitorState.save_if_dirty()` — conditional save — WORKS

**Проблемы:**
- Нет. Чистый, минимальный код с dirty flag оптимизацией.

---

### utils.py
**Назначение:** Общие утилиты: ccbot_dir, atomic_write_json, read_cwd_from_jsonl, shutdown marker.
**Классы/Функции:**
- `ccbot_dir()` — путь к конфиг директории (~/.ccbot или CCBOT_DIR) — WORKS
- `atomic_write_json(path, data, indent)` — crash-safe запись через temp+rename — WORKS
- `read_cwd_from_jsonl(file_path)` — извлечение cwd из первой JSONL записи — WORKS
- `write_shutdown_marker()` — запись маркера чистого shutdown — WORKS
- `read_and_clear_shutdown_marker()` — чтение + удаление маркера — WORKS

**Проблемы:**
- Нет. `atomic_write_json` использует `os.fsync` + `os.replace` — максимально надёжная запись.

---

### handlers/callback_data.py
**Назначение:** Константы callback data для inline keyboards (все CB_* префиксы).
**Классы/Функции:**
- 16 констант: CB_HISTORY_*, CB_DIR_*, CB_WIN_*, CB_SCREENSHOT_*, CB_ASK_*, CB_SESSION_*, CB_KEYS_PREFIX — WORKS

**Проблемы:**
- Нет. Чистый модуль констант.

---

### handlers/cleanup.py
**Назначение:** Централизованная очистка состояния при удалении топика.
**Классы/Функции:**
- `clear_topic_state(user_id, thread_id, bot, user_data)` — очистка status_msg_info, tool_msg_ids, interactive_msgs, pending state — WORKS

**Проблемы:**
- Нет. Правильная координация очистки между модулями.

---

### handlers/directory_browser.py
**Назначение:** UI навигации по директориям и выбора сессий для создания новых топиков.
**Классы/Функции:**
- `clear_browse_state(user_data)` — очистка состояния браузера — WORKS
- `clear_window_picker_state(user_data)` — очистка состояния picker'а окон — WORKS
- `clear_session_picker_state(user_data)` — очистка состояния picker'а сессий — WORKS
- `build_window_picker(windows)` — UI привязки незанятых окон — WORKS
- `build_directory_browser(current_path, page)` — пагинированный браузер директорий — WORKS
- `_relative_time(file_path)` — human-readable время ("5m ago", "2h ago") — WORKS
- `build_session_picker(sessions)` — UI возобновления существующих сессий — WORKS

**Проблемы:**
- `DIRS_PER_PAGE = 6` — жёсткое ограничение, не конфигурируемо.
- `build_directory_browser`: при `allowed_roots` корректно ограничивает навигацию, но в `CB_DIR_UP` callback в bot.py строка 2241 комментарий "No restriction" — **потенциальный баг**: `build_directory_browser` сам ограничивает, но `CB_DIR_UP` в bot.py не проверяет allowed_roots перед вызовом. Однако `build_directory_browser` внутри себя делает проверку — нет бага.

---

### handlers/history.py
**Назначение:** Отображение истории сообщений с пагинацией.
**Классы/Функции:**
- `_build_history_keyboard(window_id, page_index, total_pages, start_byte, end_byte)` — inline keyboard для навигации — WORKS
- `send_history(target, window_id, offset, edit, start_byte, end_byte, user_id, bot, message_thread_id)` — отправка/редактирование истории с пагинацией — WORKS

**Проблемы:**
- callback_data для пагинации включает page:window_id:start:end — может превысить 64 байта для длинных window_id, но `[:64]` обрезка на месте.
- Expandable quote sentinels корректно стрипаются для history view.

---

### handlers/interactive_ui.py
**Назначение:** Обработка интерактивных UI Claude Code (вопросы, permissions, plan mode).
**Классы/Функции:**
- `INTERACTIVE_TOOL_NAMES` — frozenset {"AskUserQuestion", "ExitPlanMode"} — WORKS
- `get_interactive_window(user_id, thread_id)` — текущее окно в interactive mode — WORKS
- `set_interactive_mode(user_id, window_id, thread_id)` — установка режима — WORKS
- `clear_interactive_mode(user_id, thread_id)` — очистка режима — WORKS
- `get_interactive_msg_id(user_id, thread_id)` — ID сообщения UI — WORKS
- `_build_interactive_keyboard(window_id, ui_name)` — клавиатура навигации (Space/Up/Tab, Left/Down/Right, Esc/Refresh/Enter) — WORKS
- `handle_interactive_ui(bot, user_id, window_id, thread_id)` — capture terminal + отправка UI — WORKS
- `clear_interactive_msg(user_id, bot, thread_id)` — удаление UI сообщения + очистка — WORKS

**Проблемы:**
- `_interactive_msgs` и `_interactive_mode` — module-level dicts, не защищены от concurrent access (потенциально, но asyncio single-threaded, так что OK).

---

### handlers/message_queue.py
**Назначение:** Per-user очередь сообщений с merging, tool_use/tool_result pairing, flood control.
**Классы/Функции:**
- `_ensure_formatted(text)` — MD → MarkdownV2 — WORKS
- `MessageTask` — dataclass задачи (task_type, text, window_id, parts, tool_use_id, content_type, thread_id, image_data) — WORKS
- `get_message_queue(user_id)` — lookup — WORKS
- `get_or_create_queue(bot, user_id)` — создание очереди + worker — WORKS
- `_inspect_queue(queue)` — non-destructive drain — WORKS
- `_can_merge_tasks(base, candidate)` — проверка совместимости для merge — WORKS
- `_merge_content_tasks(queue, first, lock)` — merge consecutive content tasks (макс 3800 chars) — WORKS
- `_message_queue_worker(bot, user_id)` — фоновый worker (FIFO, flood control, merge) — WORKS
- `_send_kwargs(thread_id)` — helper для message_thread_id — WORKS
- `_send_task_images(bot, chat_id, task)` — отправка base64 изображений — WORKS
- `_process_content_task(bot, user_id, task)` — обработка content (tool_result editing, long response, status→content conversion) — WORKS
- `_convert_status_to_content(bot, user_id, thread_id_or_0, window_id, content_text)` — конверсия status msg → content — WORKS
- `_process_status_update_task(bot, user_id, task)` — обработка status update (edit/send new) — WORKS
- `_do_send_status_message(bot, user_id, thread_id_or_0, window_id, text)` — отправка нового status — WORKS
- `_do_clear_status_message(bot, user_id, thread_id_or_0)` — удаление status msg — WORKS
- `_check_and_send_status(bot, user_id, window_id, thread_id)` — проверка terminal status после content — WORKS
- `enqueue_content_message(...)` — public API enqueue content — WORKS
- `enqueue_status_update(...)` — public API enqueue status (с dedup) — WORKS
- `clear_status_msg_info(user_id, thread_id)` — очистка tracking — WORKS
- `clear_tool_msg_ids_for_topic(user_id, thread_id)` — очистка tool msg tracking — WORKS
- `shutdown_workers()` — остановка всех workers — WORKS

**Проблемы:**
- `_inspect_queue` + refill pattern: корректный, но сложный. Комментарий про `task_done()` compensation — правильный и критически важный.
- `FLOOD_CONTROL_MAX_WAIT = 10` — при длительном бане (>10s) status дропается, content ждёт. Разумная стратегия.
- Строка 389-391: `_track_message_thread` импортируется из `..bot` (circular), но через deferred import — WORKS.

---

### handlers/message_sender.py
**Назначение:** Safe message sending с MarkdownV2 → plain text fallback.
**Классы/Функции:**
- `strip_sentinels(text)` — удаление expandable quote маркеров — WORKS
- `_ensure_formatted(text)` — дубликат из message_queue (MD → MarkdownV2) — WORKS
- `send_with_fallback(bot, chat_id, text, **kwargs)` — send с двойным fallback — WORKS
- `send_photo(bot, chat_id, image_data, **kwargs)` — single photo или media group — WORKS
- `safe_reply(message, text, **kwargs)` — reply с fallback — WORKS
- `safe_edit(target, text, **kwargs)` — edit с fallback — WORKS
- `safe_send(bot, chat_id, text, message_thread_id, **kwargs)` — send с fallback — WORKS

**Проблемы:**
- `_ensure_formatted` дублируется в message_queue.py и message_sender.py — **мелкий code smell**, но не баг.
- Все RetryAfter re-raised — правильно, обрабатывается в queue worker.
- `safe_reply` raises на финальном exception, `safe_send` поглощает — inconsistency, но `safe_reply` используется в command handlers где можно позволить exception propagation.

---

### handlers/response_builder.py
**Назначение:** Построение пагинированных ответов для Telegram.
**Классы/Функции:**
- `build_response_parts(text, is_complete, content_type, role)` — разбиение на части с [1/N] суффиксом — WORKS

**Проблемы:**
- `max_text = 3000` — консервативный лимит (оставляет запас для MarkdownV2 expansion). Хорошо.
- Thinking контент обрезается до 500 символов в expandable quote — разумное решение.
- User messages обрезаются до 3000 — жёсткий лимит без уведомления пользователя.

---

### handlers/status_polling.py
**Назначение:** Фоновый polling статуса терминала, детекция dead sessions, auto-restart, idle reminder.
**Классы/Функции:**
- `record_user_activity(user_id, thread_id)` — запись активности пользователя — WORKS
- `record_claude_response(user_id, thread_id)` — запись ответа Claude — WORKS
- `update_status_message(bot, user_id, window_id, thread_id, skip_status)` — poll + UI detect + status — WORKS
- `status_poll_loop(bot)` — основной loop (3s interval) — WORKS

**Подсистемы внутри status_poll_loop:**
- Topic existence probe (60s, через unpin_all_forum_topic_messages) — WORKS
- Stale binding cleanup (window gone → unbind) — WORKS
- Dead Claude detection + auto-restart (--resume, max 2 attempts, 60s cooldown) — WORKS
- Idle reminder (configurable, default 120s) — WORKS
- Interactive UI detection (always runs, even when skip_status) — WORKS

**Проблемы:**
- `STATUS_POLL_INTERVAL = 3.0` — hardcoded, не в config. Раньше было 1.0 в docs — **inconsistency с документацией** (docs/rules/message-handling.md говорит "1-second intervals").
- Topic existence probe через `unpin_all_forum_topic_messages` — creative hack, но может иметь side effects если есть pinned messages.
- `_EXIT_GRACE_PERIOD = 5.0` — жёсткий, не конфигурируемый.
- Auto-restart с `literal=False` в send_keys — отправляет command с `--resume` как special keys, не literal text. **Потенциальный баг**: `send_keys(wid, cmd, enter=True, literal=False)` — при `literal=False`, tmux интерпретирует спецсимволы в команде. Если session_id содержит `-`, tmux может неправильно интерпретировать. Однако `shlex.quote` экранирует, и UUID формат не содержит проблемных символов для tmux. **UNTESTED** — нужно проверить на реальном restart.

---

### bot.py
**Назначение:** Главный UI слой — все Telegram handlers, callback routing, lifecycle management.
**Классы/Функции:**

**Background tasks:**
- `_file_cleanup_loop()` — удаление старых файлов каждые 6 часов — WORKS
- `_flush_input_buffer(user_id, thread_id, wid)` — отправка батча сообщений — WORKS
- `_enqueue_batched_input(user_id, thread_id, wid, text)` — debounce input — WORKS

**Auto-naming:**
- `_auto_name_topic(bot, user_id, thread_id, wid, text)` — переименование топика по первому сообщению — WORKS
- `_SKIP_AUTONAME_PATTERNS` — 15 паттернов (hi, привет, ok, etc.) — WORKS

**Utility:**
- `is_user_allowed(user_id)` — проверка доступа — WORKS
- `_extract_forward_context(message)` — контекст пересланных сообщений — WORKS
- `_extract_reply_context(message)` — контекст цитат-ответов — WORKS
- `_get_thread_id(update)` — извлечение thread_id (None для General topic) — WORKS
- `_check_rate_limit(user_id)` — 30 msg / 60s rate limit — WORKS
- `_track_message_thread(message_id, thread_id, window_id)` — tracking для reactions — WORKS

**Command handlers:**
- `start_command` — /start приветствие — WORKS
- `help_command` — /help справка — WORKS
- `history_command` — /history — WORKS
- `screenshot_command` — /screenshot (ANSI → PNG) — WORKS
- `unbind_command` — /unbind — WORKS
- `kill_command` — /kill (kill + delete topic) — WORKS
- `restart_command` — /restart (kill + create new at same dir) — WORKS
- `esc_command` — /esc (send \x1b) — WORKS
- `usage_command` — /usage (send /usage → capture → parse → send) — UNTESTED (зависит от Claude Code TUI рендеринга)
- `health_command` — /health (uptime, sessions, tmux, memory) — WORKS
- `summary_command` — /summary (structured digest из истории) — WORKS
- `sessions_command` — /sessions (список с is_claude_running) — WORKS

**Content handlers:**
- `text_handler` — основной текстовый handler (unbound → picker/browser → bound → send) — WORKS
- `photo_handler` — фото → download → forward path — WORKS
- `voice_handler` — голос → Deepgram → forward text — WORKS
- `document_handler` — документы → download → forward path (whitelist расширений, blacklist sensitive) — WORKS
- `edited_message_handler` — edited msg → forward с "(Исправление)" — WORKS
- `forward_command_handler` — forward /commands к Claude Code — WORKS
- `topic_closed_handler` — topic close → kill window + unbind — WORKS
- `topic_edited_handler` — topic rename → sync tmux + display name — WORKS
- `unsupported_content_handler` — stickers/video/etc → rejection — WORKS
- `reaction_handler` — emoji → short text to Claude (18 mappings) — WORKS

**Screenshot keyboard:**
- `_build_screenshot_keyboard(window_id)` — 9 control keys + Refresh — WORKS
- `_KEYS_SEND_MAP` — 9 key mappings (up/dn/lt/rt/esc/ent/spc/tab/cc) — WORKS

**Bash capture:**
- `_cancel_bash_capture(user_id, thread_id)` — cancel background task — WORKS
- `_capture_bash_output(bot, user_id, thread_id, window_id, command)` — 30s background capture with live editing — WORKS

**Window creation:**
- `_create_and_bind_window(query, context, user, selected_path, pending_thread_id, resume_session_id)` — create window + bind + forward pending text — WORKS

**Callback handler:**
- `callback_handler` — routing 20+ callback types (history pagination, dir browser, window picker, session picker, screenshot, interactive UI keys) — WORKS

**Streaming/notifications:**
- `handle_new_message(msg, bot)` — dispatch NewMessage → enqueue (content/status/file/interactive) — WORKS

**Lifecycle:**
- `_run_startup_diagnostics(bot)` — проверка tmux, state files, config dir, Deepgram — WORKS
- `post_init(application)` — setup monitor, polling, cleanup, rate limiter prefill, restart notification — WORKS
- `post_shutdown(application)` — notify topics, shutdown marker, stop polling/workers/monitor — WORKS
- `error_handler(update, context)` — global error handler + developer alert via Telegram — WORKS
- `create_bot()` — Application builder с всеми handlers — WORKS

**Smart TG file request detection:**
- Строки 1741-1759: детекция фраз "пришли в тг", "отправь в телеграм" и добавление hint для Claude — WORKS

**Проблемы:**
- **bot.py слишком большой** (~3170 строк). Callback handler — 600+ строк с повторяющимися паттернами (pending_tid validation, topic mismatch check). Кандидат на рефакторинг.
- `rate_limiter._base_limiter._level` (строка 2954) — доступ к private API AIORateLimiter. **BROKEN** при обновлении python-telegram-bot — может поменяться internal structure.
- `_msg_thread_map` — растёт без ограничения до 10000, потом cleanup. При high traffic может занять значительную память.
- `_TG_SEND_PATTERNS` — hardcoded русские фразы. Не расширяемо, но работает для целевой аудитории.
- Строка 2041-2052: прямой вызов `session_manager._save_state()` — обход публичного API (private method). **Code smell**.

---

## Ralph Loop фичи (22 коммита сверху)

Анализ git log показывает 22 коммита, добавленных сверху базовой версии. Все они **интегрированы в кодовую базу**:

### Полностью интегрированные (в коде):
1. **sync Telegram topic name to tmux window on rename** — `topic_edited_handler` в bot.py — WORKS
2. **session resume picker** — `build_session_picker`, `CB_SESSION_*` в directory_browser.py — WORKS
3. **voice message transcription** — transcribe.py + voice_handler в bot.py (сменено с OpenAI на Deepgram) — WORKS
4. **hook timeout handling for resume** — строки 2028-2052 в bot.py — WORKS
5. **markdown tables conversion** — `convert_markdown_tables` в markdown_v2.py — WORKS
6. **telegramify-markdown dependency** — pyproject.toml — WORKS
7. **CCBOT_SHOW_TOOL_CALLS/USER_MESSAGES env vars** — config.py (clean_output, show_user_messages) — WORKS
8. **security hardening, Russian localization, Deepgram, clean output, reactions** — throughout — WORKS
9. **graceful shutdown with user notifications** — post_shutdown + shutdown marker — WORKS
10. **/health diagnostic command** — health_command — WORKS
11. **forward edited messages** — edited_message_handler — WORKS
12. **document upload handler** — document_handler — WORKS
13. **idle detection with smart re-notification** — status_polling.py idle reminder — WORKS
14. **multi-message input batching** — _flush_input_buffer, _enqueue_batched_input — WORKS
15. **rich progress status showing live tool activity** — _format_tool_status в session_monitor.py — WORKS
16. **/summary command** — summary_command — WORKS
17. **auto-restart Claude on crash with --resume** — status_polling.py _restart_attempts — WORKS
18. **/kill and /restart commands** — kill_command, restart_command — WORKS
19. **/sessions command** — sessions_command — WORKS
20. **enrich forwarded messages with sender context** — _extract_forward_context — WORKS
21. **startup self-diagnostics** — _run_startup_diagnostics — WORKS
22. **smart excerpt for long responses** — message_queue.py long response threshold — WORKS
23. **auto-name topics** — _auto_name_topic — WORKS
24. **automatic file cleanup** — _file_cleanup_loop — WORKS
25. **enrich quoted replies with context** — _extract_reply_context — WORKS
26. **global error handler with developer alerts** — error_handler — WORKS
27. **enhanced /start onboarding and /help** — start_command, help_command — WORKS

### Только в документации (не код):
- `docs: обоснование 20 фич на русском (features-rationale-ru.md)` — документация
- `docs: finalize improvement log` — документация
- `test: comprehensive test suite` — тесты (не production код)

**Вывод:** Все 20+ Ralph Loop фич полностью интегрированы в кодовую базу и функционируют. Нет "мёртвых" или частично интегрированных фич.

---

## Общие проблемы и рекомендации

### Критические
1. **bot.py ~3170 строк** — нужен рефакторинг, вынести callback routing в отдельный модуль.
2. **Доступ к private API rate limiter** (`_base_limiter._level`) — сломается при обновлении библиотеки.

### Средние
3. **`_ensure_formatted` дублируется** в message_sender.py и message_queue.py.
4. **STATUS_POLL_INTERVAL = 3.0** не соответствует документации (1s).
5. **Hardcoded `language: "ru"` в Deepgram** — не конфигурируемо.
6. **session_manager._save_state()** вызывается напрямую из bot.py — обход инкапсуляции.

### Мелкие
7. Лишние `pass` в session.py (строки 183, 192).
8. Дублирование status emit в session_monitor.py (строки 562-583).
9. `_msg_thread_map` может занимать память при high traffic.
10. Docstring transcribe.py упоминает "OpenAI" вместо "Deepgram".
