# Аудит версии malovlab/ccbot

## Сводка
- **Репозиторий:** https://github.com/malovlab/ccbot
- **Коммит:** `f6fff4a` (единственный коммит)
- **Автор:** kokobongafreakr222 <kokobongafreakr222@protonmail.com>
- **Дата:** 2026-03-20
- **Описание коммита:** "feat: ccbot restored from installed version (newer than malovnik/ccbot)"
- **Всего исходных файлов (src/ccbot/):** 28 файлов
- **НОВЫЕ файлы (нет в malovnik):** `ws_bridge.py`, `ws_protocol.py`, `terminal_stream.py`
- **ИЗМЕНЁННЫЕ файлы:** `main.py`, `config.py`, `hook.py`, `bot.py`, `session_monitor.py`
- **УДАЛЁННЫЕ файлы (есть в malovnik, нет в malovlab):** нет

---

## Новые модули

### ws_bridge.py (664 строк)

**Назначение:** WebSocket bridge сервер, соединяющий веб-фронтенд с внутренней логикой CCBot. Работает в том же asyncio event loop, что и Telegram бот, разделяя SessionManager и TmuxManager.

**Классы:**

| Класс | Назначение |
|-------|-----------|
| `_ClientState` | Состояние одного WS-клиента: аутентификация, подписки на терминалы, rate limiting, pending upload |
| `WsBridge` | Основной сервер: управление подключениями, аутентификация, маршрутизация сообщений |

**Ключевые методы WsBridge:**

| Метод | Назначение |
|-------|-----------|
| `start()` | Запуск WebSocket сервера (websockets.serve) |
| `stop()` | Остановка сервера и всех подключений |
| `broadcast()` | Отправка сообщения всем аутентифицированным клиентам (с фильтрацией по window_id) |
| `on_new_message()` | Callback от SessionMonitor — пересылка сообщений Claude в WS клиенты |
| `_handle_connection()` | Обработка одного WS-подключения (auth, rate limit, dispatch) |
| `_dispatch()` | Маршрутизация parsed-сообщений к обработчикам через match/case |
| `_handle_auth()` | HMAC-аутентификация по токену (localhost без токена разрешён) |
| `_handle_list_sessions()` | Список активных tmux окон с сессиями |
| `_handle_create_session()` | Создание новой сессии с проверкой ALLOWED_ROOTS |
| `_handle_resume_session()` | Возобновление сессии по session_id |
| `_handle_kill_session()` | Завершение сессии |
| `_handle_send_message()` | Отправка текста в Claude через SessionManager |
| `_handle_send_key()` | Отправка клавиши в tmux (белый список: Escape, Tab, Arrow keys и т.д.) |
| `_handle_get_history()` | Чтение JSONL истории сессии с парсингом tool_use, thinking, file messages |
| `_handle_browse_directory()` | Навигация по директориям (с проверкой ALLOWED_ROOTS) |
| `_handle_binary()` | Обработка бинарных фреймов: загрузка файлов или voice transcription |
| `_save_uploaded_file()` | Сохранение загруженного файла (max 50MB, sanitized filename) |
| `_on_terminal_data()` | Callback от TerminalStreamer — broadcast терминального вывода |

**Архитектура WebSocket Bridge:**
- Singleton `ws_bridge` на уровне модуля (None по умолчанию, создаётся в main.py)
- Rate limiting: 60 сообщений/минуту на подключение
- Max подключений: 20
- Auth через HMAC compare_digest (CCBOT_WS_TOKEN)
- Localhost без токена разрешён
- Поддержка binary frames: voice transcription через Deepgram + file upload
- Terminal streaming через TerminalStreamer (подписка/отписка по window_id)

**Безопасность:**
- HMAC-based auth для non-localhost
- Rate limiting per-connection
- ALLOWED_ROOTS enforcement для create_session и browse_directory
- Whitelist клавиш для send_key
- Sanitization имён файлов при upload
- Max file size 50MB

---

### ws_protocol.py (301 строка)

**Назначение:** Типизированные определения сообщений для WebSocket протокола. Dataclasses для type safety и JSON сериализации.

**Client -> Server сообщения (14 типов):**

| Dataclass | type | Назначение |
|-----------|------|-----------|
| `WsAuth` | `auth` | Аутентификация по токену |
| `WsListSessions` | `list_sessions` | Запрос списка сессий |
| `WsCreateSession` | `create_session` | Создание новой сессии (path) |
| `WsResumeSession` | `resume_session` | Возобновление сессии (session_id + path) |
| `WsKillSession` | `kill_session` | Завершение сессии (window_id) |
| `WsSendMessage` | `send_message` | Отправка текста в Claude (window_id + text) |
| `WsSendKey` | `send_key` | Отправка клавиши (window_id + key) |
| `WsGetHistory` | `get_history` | Запрос истории (window_id + offset) |
| `WsBrowseDirectory` | `browse_directory` | Навигация по директориям (path) |
| `WsSubscribeTerminal` | `subscribe_terminal` | Подписка на терминал (window_id) |
| `WsUnsubscribeTerminal` | `unsubscribe_terminal` | Отписка от терминала (window_id) |
| `WsCaptureTerminal` | `capture_terminal` | Разовый capture терминала (window_id) |
| `WsUploadFile` | `upload_file` | Начало загрузки файла (window_id + file_name) |
| `WsPing` | `ping` | Проверка связи |

**Server -> Client сообщения (12 типов):**

| Dataclass | type | Назначение |
|-----------|------|-----------|
| `WsAuthResult` | `auth_result` | Результат аутентификации |
| `WsSessionList` | `session_list` | Список сессий |
| `WsSessionCreated` | `session_created` | Новая сессия создана |
| `WsSessionEnded` | `session_ended` | Сессия завершена |
| `WsMessage` | `message` | Сообщение (role, content, content_type, tool_name) |
| `WsFileMessage` | `file` | Файловое сообщение (file_path, download_url) |
| `WsStatus` | `status` | Статус (tool в процессе / thinking) |
| `WsStatusClear` | `status_clear` | Сброс статуса |
| `WsInteractiveUi` | `interactive_ui` | Интерактивный UI |
| `WsTerminalData` | `terminal_data` | Данные терминала (ANSI) |
| `WsDirectoryListing` | `directory_listing` | Список директорий |
| `WsHistory` | `history` | История сообщений |
| `WsError` | `error` | Ошибка (code + message) |
| `WsPong` | `pong` | Ответ на ping |

**Утилиты:**
- `serialize(msg)` — dataclass -> JSON string
- `parse_client_message(raw)` — JSON string -> typed dataclass (с валидацией типов полей)
- `_CLIENT_MSG_MAP` — маппинг type string -> dataclass class

---

### terminal_stream.py (99 строк)

**Назначение:** Периодический capture tmux pane с diff-based доставкой. Только изменённый контент отправляется подписанным WebSocket клиентам.

**Класс: TerminalStreamer**

| Метод | Назначение |
|-------|-----------|
| `__init__(on_data)` | Инициализация с async callback(window_id, ansi_text) |
| `subscribe(window_id)` | Добавление подписчика, запуск capture loop (max 10 per window) |
| `unsubscribe(window_id)` | Удаление подписчика, остановка loop при count=0 |
| `unsubscribe_all(window_id)` | Удаление всех подписчиков для окна |
| `stop()` | Отмена всех streaming задач |
| `_capture_loop(window_id)` | Цикл: capture_pane каждые 200ms, emit при изменении |

**Константы:**
- `CAPTURE_INTERVAL = 0.2` (200ms)
- `MAX_SUBSCRIBERS_PER_WINDOW = 10`

**Архитектура:** Каждое окно имеет свою asyncio Task, которая стартует при первой подписке и останавливается при нулевом количестве подписчиков. Diff-based: сохраняется last_content, отправка только при изменении.

---

## Изменённые модули

### main.py

**Что изменилось:**
1. **Новый режим `ccbot web`** — запуск WS bridge без Telegram бота (`_run_web_only()`)
2. **Флаг `--with-web`** — запуск WS bridge параллельно с Telegram ботом
3. **Рефакторинг логирования** — вынесен в отдельную функцию `_setup_logging()`
4. **Docstring обновлён** — описывает 3 режима вместо 2
5. **Версия из metadata** — выводит `CCBot v{version}` при старте
6. **Логика запуска WS bridge** — если `--with-web` или `config.ws_enabled`, создаёт WsBridge singleton

**Новые функции:**
- `_setup_logging()` — конфигурация логирования (console + file rotation)
- `_run_web_only()` — standalone WS bridge режим

### config.py

**Что изменилось:**
1. **CCBOT_WS_TOKEN добавлен в SENSITIVE_ENV_VARS** — скрабится из os.environ
2. **Новые конфиг-параметры для WS:**
   - `ws_enabled` (CCBOT_WS_ENABLED, default False)
   - `ws_port` (CCBOT_WS_PORT, default 8765)
   - `ws_host` (CCBOT_WS_HOST, default "127.0.0.1")
   - `ws_token` (CCBOT_WS_TOKEN)

### hook.py

**Что изменилось:**
1. **Новая функция `_update_hook_path()`** — обновляет путь к ccbot в hook config при изменении
2. **`_install_hook()` расширен** — при уже установленном хуке проверяет, не изменился ли путь, и обновляет его

### bot.py

**Что изменилось:**
1. **WS bridge интеграция** — в конце `create_bot()` (примерно строка 2963+) добавлен блок:
   - Импорт `ws_bridge` singleton
   - Если WS bridge активен: запуск `asyncio.create_task(_ws_bridge.start())`
   - Регистрация `_ws_bridge.on_new_message` как callback в мониторе через `monitor.add_message_callback()`

### session_monitor.py

**Что изменилось:**
1. **Множественные callbacks** — `_message_callback` (единичный) заменён на `_message_callbacks` (список)
2. **Новый метод `add_message_callback()`** — добавляет дополнительный callback (для WS bridge)
3. **`set_message_callback()` сохранён** — backward-compatible, заменяет первый элемент списка
4. **Цикл вызова callbacks** — вместо одного вызова, итерация по всем callbacks
5. **Улучшен формат логирования** — `f"Message callback error: {e}"` заменён на `"Message callback error: %s", e`

---

## Файлы без изменений

Все остальные модули идентичны между версиями:
- `__init__.py`, `markdown_v2.py`, `monitor_state.py`, `screenshot.py`
- `session.py`, `telegram_sender.py`, `terminal_parser.py`, `tmux_manager.py`
- `transcribe.py`, `transcript_parser.py`, `utils.py`
- `handlers/__init__.py`, `handlers/callback_data.py`, `handlers/cleanup.py`
- `handlers/directory_browser.py`, `handlers/history.py`, `handlers/interactive_ui.py`
- `handlers/message_queue.py`, `handlers/message_sender.py`, `handlers/response_builder.py`
- `handlers/status_polling.py`

---

## Зависимости (pyproject.toml)

**Различие:** В malovlab отсутствует секция `[dependency-groups]` с dev-зависимостями:
```
pip-audit>=2.10.0
pytest>=9.0.2
pytest-asyncio>=1.3.0
ruff>=0.15.6
```
Основные (runtime) зависимости идентичны.

**Примечание:** В malovlab добавлены `websockets` и `aiofiles` как runtime-зависимости (используются ws_bridge.py и ws_bridge.py -> get_history).

---

## Тесты

**Только в malovnik:** `tests/ccbot/test_new_features.py`
**Различия:** `tests/ccbot/test_transcribe.py`, `tests/ccbot/test_utils.py` имеют незначительные отличия.
**Нет тестов для:** `ws_bridge.py`, `ws_protocol.py`, `terminal_stream.py` (новые модули без покрытия).
