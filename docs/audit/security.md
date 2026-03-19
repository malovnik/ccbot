# Security Аудит CCBot

**Дата:** 2026-03-20
**Аудитор:** Claude Opus 4.6
**Версия:** 0.1.0
**Коммит:** текущий HEAD

---

## Сводка

- **HIGH: 2 issues**
- **MEDIUM: 4 issues**
- **LOW: 4 issues**

Общая оценка: проект демонстрирует хорошую security-осведомленность (scrubbing env vars, allowed_roots, rate limiting, UUID validation, hmac.compare_digest). Критических уязвимостей, позволяющих удалённое выполнение кода неаутентифицированным атакующим, не обнаружено. Найденные проблемы связаны с неполным покрытием валидации в WS bridge и потенциальными information disclosure.

---

## Findings

### [HIGH] Отсутствие проверки allowed_roots в WS resume_session

**Файл:** `src/ccbot/ws_bridge.py:424-444`
**Описание:** Обработчик `_handle_resume_session` не проверяет `msg.path` против `config.allowed_roots`. В отличие от `_handle_create_session` (строка 384-393) и `_handle_browse_directory` (строка 668-676), где проверка есть, resume_session позволяет аутентифицированному WS-клиенту создать tmux окно в произвольной директории. Это обходит boundary restriction, установленный через `CCBOT_ALLOWED_ROOTS`.
**Рекомендация:** Добавить проверку `allowed_roots` в `_handle_resume_session` аналогично `_handle_create_session`:
```python
if not any(path == root or str(path).startswith(str(root) + "/") for root in config.allowed_roots):
    await self._send(client, WsError(code="access_denied", message="Path outside allowed roots"))
    return
```
**Статус:** OPEN

---

### [HIGH] WS file download_url содержит полный путь без серверной валидации

**Файл:** `src/ccbot/ws_bridge.py:176`
**Описание:** При обнаружении Write tool, WS bridge формирует `download_url=f"/api/file?path={str(fpath)}"` и отправляет клиенту. Однако никакого HTTP-сервера, обслуживающего `/api/file`, в кодовой базе нет. Это создает два риска:
1. Если фронтенд реализует этот endpoint в будущем без валидации, возникнет path traversal.
2. Полный серверный путь (`file_path`) отправляется WS-клиенту через `WsFileMessage`, раскрывая файловую структуру сервера.
**Рекомендация:** Убрать `download_url` с полным путём. Реализовать безопасный file-serving через токенизированные ссылки, либо отдавать содержимое файла через WS бинарным фреймом с проверкой allowed_roots.
**Статус:** OPEN

---

### [MEDIUM] WS send_message не имеет ограничения длины текста

**Файл:** `src/ccbot/ws_bridge.py:461-466`
**Описание:** `_handle_send_message` передает `msg.text` напрямую в `session_manager.send_to_window`, который ограничивает длину до 4096 символов (session.py:814-819). Однако WS-сообщение может быть до 1 МБ (`max_size=2**20`, строка 115). Парсинг и обработка мегабайтного JSON с длинным полем text потребляет память до отсечки в send_to_window.
**Рекомендация:** Добавить валидацию длины `msg.text` в WS-обработчике до передачи в session_manager:
```python
if len(msg.text) > 4096:
    await self._send(client, WsError(code="too_long", message="Message too long"))
    return
```
**Статус:** OPEN

---

### [MEDIUM] WS localhost bypass позволяет доступ без токена

**Файл:** `src/ccbot/ws_bridge.py:327-347`
**Описание:** При `ws_host in ("127.0.0.1", "localhost", "::1")` и отсутствии `CCBOT_WS_TOKEN`, любой клиент на том же хосте получает доступ без аутентификации. В shared-hosting или container-среде (Docker, Railway) localhost может быть доступен другим процессам/контейнерам. Кроме того, проверка `config.ws_host` основана на конфигурации bind-адреса, а не на реальном адресе подключившегося клиента.
**Рекомендация:** Всегда требовать `CCBOT_WS_TOKEN`, если WS включен. Убрать localhost bypass. Логировать warning при запуске WS без токена.
**Статус:** OPEN

---

### [MEDIUM] Передача file_path клиенту через WsFileMessage раскрывает серверные пути

**Файл:** `src/ccbot/ws_bridge.py:167-179` и `ws_bridge.py:569-597` (history handler)
**Описание:** `WsFileMessage` содержит `file_path=str(fpath)` — полный абсолютный путь на сервере. В history handler аналогично передаётся `file_path` (строка 592). Это information disclosure: WS-клиент узнаёт структуру файловой системы сервера, имена пользователей, расположение проектов.
**Рекомендация:** Не передавать полные серверные пути клиенту. Использовать токенизированные идентификаторы или относительные пути.
**Статус:** OPEN

---

### [MEDIUM] Отсутствие проверки path.is_dir() в WS resume_session

**Файл:** `src/ccbot/ws_bridge.py:427`
**Описание:** `_handle_resume_session` вызывает `Path(msg.path).expanduser().resolve()`, но не проверяет, что результат — существующая директория (в отличие от `_handle_create_session`, строка 377). `tmux_manager.create_window` проверяет это (строки 439-443), но несогласованность в слоях валидации увеличивает поверхность атаки.
**Рекомендация:** Добавить `if not path.is_dir()` проверку в начало обработчика, как в `_handle_create_session`.
**Статус:** OPEN

---

### [LOW] Deepgram API key передается через HTTP без проверки ответа сервера

**Файл:** `src/ccbot/transcribe.py:38-51`
**Описание:** API key передается в заголовке Authorization. При ошибке HTTP (401, 500), `response.raise_for_status()` выбрасывает исключение, содержащее URL и потенциально заголовки в traceback. При `logger.error` в voice_handler (bot.py:1488) полное исключение может попасть в логи.
**Рекомендация:** Оборачивать `raise_for_status()` в try/except и логировать только status code без заголовков.
**Статус:** OPEN

---

### [LOW] document_handler не проверяет содержимое файла (только расширение)

**Файл:** `src/ccbot/bot.py:1530-1548`
**Описание:** Валидация входящих документов основана исключительно на расширении файла и имени. Атакующий (с доступом к боту) может переименовать исполняемый файл в `.txt` и загрузить его. Однако поскольку файл просто сохраняется в `~/.ccbot/documents/` и его путь передается Claude Code как текст, реальный риск минимален — Claude Code сам решает, что делать с файлом.
**Рекомендация:** Для усиления можно добавить magic-bytes проверку через `python-magic`, но приоритет низкий из-за модели угроз (только авторизованные пользователи).
**Статус:** OPEN

---

### [LOW] Таймаут для WS аутентификации отсутствует

**Файл:** `src/ccbot/ws_bridge.py:215-264`
**Описание:** После подключения WS-клиент может оставаться неаутентифицированным неограниченное время, занимая один из 20 слотов `_MAX_CONNECTIONS`. Злоумышленник может открыть 20 соединений без аутентификации и заблокировать доступ легитимным клиентам.
**Рекомендация:** Добавить таймаут аутентификации (например, 30 секунд), после которого неаутентифицированные соединения закрываются.
**Статус:** OPEN

---

### [LOW] Имя загруженного файла через WS не ограничено по длине

**Файл:** `src/ccbot/ws_bridge.py:770`
**Описание:** `file_name` из `WsUploadFile` санитизируется (`_save_uploaded_file`, строка 770), но не ограничивается по длине. Очень длинное имя файла (тысячи символов) может создать проблемы с файловой системой.
**Рекомендация:** Ограничить `safe_name` до 255 символов (лимит большинства FS).
**Статус:** OPEN

---

## Проверенные области (без замечаний)

### Secrets Management
- `.gitignore` корректно включает `.env` и `.venv` — OK
- `.env.example` содержит только placeholder-значения (`your_bot_token_here`, `your_telegram_user_id`) — OK
- `SENSITIVE_ENV_VARS` скрабит 6 переменных из `os.environ` после загрузки (config.py:22-28, 167-168) — OK
- Дополнительно: `_scrub_session_env` удаляет чувствительные переменные из tmux session environment (tmux_manager.py:87-98) — OK
- Git-история не содержит коммитов `.env` или файлов с секретами — OK
- Hardcoded секретов в коде не обнаружено — OK

### Command Injection (tmux)
- `tmux_manager.send_keys`: для literal-режима используется `pane.send_keys(chars, literal=True)` через libtmux, что безопасно передает текст — OK
- `tmux_manager.capture_pane`: `asyncio.create_subprocess_exec` с аргументами как списком (не shell=True) — OK
- `tmux_manager.create_window`: `resume_session_id` валидируется через UUID regex (строка 434), `shlex.quote` для безопасной подстановки в команду (строка 476) — OK
- `hook.py`: `subprocess.run` с аргументами как списком (строка 229-239) — OK
- `is_claude_running`: `pgrep -P` с PID из tmux — безопасно, аргументы как список — OK
- WS `_handle_send_key`: жёсткий whitelist клавиш через `_ALLOWED_KEYS` frozenset (строка 468-486) — OK

### Bot Security (ALLOWED_USERS)
- Все command handlers проверяют `is_user_allowed(user.id)` — OK
- `callback_handler` проверяет авторизацию (строка 2124) — OK
- `text_handler`, `photo_handler`, `voice_handler`, `document_handler` — все проверяют — OK
- `edited_message_handler` проверяет (строка 1951) — OK
- `reaction_handler` проверяет (строка 1288) — OK
- `topic_closed_handler`, `topic_edited_handler` проверяют — OK
- `forward_command_handler` проверяет — OK
- Rate limiting: 30 msg/60s per user через `_check_rate_limit` — OK

### Directory Browser (Path Traversal)
- `build_directory_browser`: проверка `is_relative_to(root)` для `allowed_roots` (строка 133-136) — OK
- Навигация вверх блокируется на границе `allowed_roots` (строка 188-189) — OK
- `CB_DIR_CONFIRM` дополнительно проверяет `allowed_roots` (bot.py:2307-2312) — OK
- Callback-индексы проверяются на bounds (строка 2196-2200) — OK

### Screenshot
- `screenshot.py` — чистый рендерер, принимает текст и рисует PNG, файловый доступ только к бандленным шрифтам — OK

### File Sending (session_monitor)
- Write tool detection проверяет `allowed_roots` (строка 513-518) — OK
- Sensitive filenames блокируются (`_SENSITIVE_NAMES`: .env, credentials, id_rsa) — OK
- Файлы из `config_dir` блокируются (строка 521-522) — OK
- bot.py file sending дополнительно проверяет `allowed_roots` (строка 2783-2786) — OK

### WebSocket Security (базовая)
- Аутентификация через `hmac.compare_digest` (timing-safe) — OK
- Rate limiting: 60 msg/min per connection — OK
- Max connections: 20 — OK
- Max message size: 1 МБ — OK
- Max file upload: 50 МБ — OK
- File name sanitization при upload — OK
- Type validation в `parse_client_message` (string field checks) — OK

### Dependencies
- `pip-audit`: нет известных уязвимостей в зависимостях — OK

---

## Исправления (2026-03-20)

### FIXED:
1. ✅ **[HIGH]** `_handle_resume_session` — добавлена проверка `allowed_roots` + `is_dir()`
2. ✅ **[HIGH]** Полные серверные пути заменены на `~`-relative в WS-сообщениях, `download_url` очищен
3. ✅ **[MEDIUM]** Добавлен auth timeout 30 секунд для WS соединений
4. ✅ **[MEDIUM]** Добавлено ограничение длины `msg.text` (4096 chars) в `_handle_send_message`
5. ✅ **[LOW]** Ограничение длины `safe_name` до 255 символов при загрузке файлов

### Остаётся OPEN:
- **[MEDIUM]** localhost bypass без токена — по дизайну для удобства локальной разработки
- **[MEDIUM]** `_handle_resume_session` path validation vs `_handle_create_session` — теперь согласовано (FIXED)
- **[LOW]** Deepgram API key в traceback — минимальный риск
- **[LOW]** document_handler проверяет только расширение — минимальный риск (только авторизованные юзеры)
