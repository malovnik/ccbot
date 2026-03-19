# Сравнение версий: malovnik vs malovlab

**Дата аудита:** 2026-03-20
**malovnik:** локальная версия в `/Users/malovnik/Documents/Dev/ccbot/`
**malovlab:** `github.com/malovlab/ccbot` коммит `f6fff4a`

---

## Только в malovnik (нет в malovlab)

### Исходный код
- Нет отсутствующих модулей — все файлы malovnik присутствуют в malovlab

### Тесты
- `tests/ccbot/test_new_features.py` — отсутствует в malovlab

### Конфигурация
- `[dependency-groups]` секция в `pyproject.toml` — dev-зависимости (pytest, ruff, pip-audit, pytest-asyncio)

---

## Только в malovlab (нет в malovnik)

### Исходный код (3 новых модуля, 1064 строк суммарно)

| Файл | Строк | Назначение |
|------|-------|-----------|
| `ws_bridge.py` | 664 | WebSocket bridge сервер для веб-фронтенда |
| `ws_protocol.py` | 301 | Типизированные WS-сообщения (26 dataclass-типов) |
| `terminal_stream.py` | 99 | Периодический capture терминала с diff-доставкой |

### Новая функциональность
- **Режим `ccbot web`** — standalone WS bridge без Telegram бота
- **Флаг `--with-web`** — параллельный запуск WS bridge с ботом
- **Конфиг-параметры:** `CCBOT_WS_ENABLED`, `CCBOT_WS_PORT`, `CCBOT_WS_HOST`, `CCBOT_WS_TOKEN`

---

## В обоих (с различиями)

### 1. main.py
- **malovnik:** 93 строки, 2 режима (hook / default)
- **malovlab:** 161 строка, 3 режима (hook / web / default с --with-web)
- **Суть:** добавлен WS bridge lifecycle, рефакторинг logging в отдельную функцию, вывод версии

### 2. config.py
- **malovnik:** 178 строк, SENSITIVE_ENV_VARS содержит 5 переменных
- **malovlab:** 185 строк, SENSITIVE_ENV_VARS содержит 6 переменных (+CCBOT_WS_TOKEN)
- **Суть:** +4 конфиг-параметра для WS (ws_enabled, ws_port, ws_host, ws_token)

### 3. hook.py
- **malovnik:** 277 строк
- **malovlab:** 309 строк (+32)
- **Суть:** новая функция `_update_hook_path()`, расширенная логика `_install_hook()` — обновление пути при его изменении

### 4. bot.py
- **malovnik:** ~2962 строки (до конца create_bot)
- **malovlab:** ~2971 строк (+9)
- **Суть:** +9 строк в конце `create_bot()` для запуска WS bridge и регистрации callback

### 5. session_monitor.py
- **malovnik:** single callback (`_message_callback`)
- **malovlab:** multiple callbacks (`_message_callbacks` list + `add_message_callback()`)
- **Суть:** поддержка нескольких потребителей сообщений (Telegram + WS bridge), улучшен формат логирования

### 6. pyproject.toml
- **malovnik:** содержит `[dependency-groups]` с dev-зависимостями
- **malovlab:** без dev-зависимостей
- **Примечание:** runtime-зависимости в malovlab предположительно включают `websockets` и `aiofiles` (используются новыми модулями)

### 7. Тесты (незначительные различия)
- `tests/ccbot/test_transcribe.py` — незначительные отличия
- `tests/ccbot/test_utils.py` — незначительные отличия

---

## В обоих (идентичные)

### Исходный код (21 файл)
- `__init__.py`
- `markdown_v2.py`
- `monitor_state.py`
- `screenshot.py`
- `session.py`
- `telegram_sender.py`
- `terminal_parser.py`
- `tmux_manager.py`
- `transcribe.py`
- `transcript_parser.py`
- `utils.py`
- `handlers/__init__.py`
- `handlers/callback_data.py`
- `handlers/cleanup.py`
- `handlers/directory_browser.py`
- `handlers/history.py`
- `handlers/interactive_ui.py`
- `handlers/message_queue.py`
- `handlers/message_sender.py`
- `handlers/response_builder.py`
- `handlers/status_polling.py`

### Тесты (идентичные)
- `tests/conftest.py`
- `tests/ccbot/conftest.py`
- `tests/ccbot/test_config.py`
- `tests/ccbot/test_forward_command.py`
- `tests/ccbot/test_hook.py`
- `tests/ccbot/test_markdown_v2.py`
- `tests/ccbot/test_monitor_state.py`
- `tests/ccbot/test_session.py`
- `tests/ccbot/test_session_monitor.py`
- `tests/ccbot/test_telegram_sender.py`
- `tests/ccbot/test_terminal_parser.py`
- `tests/ccbot/test_transcript_parser.py`
- `tests/integration/test_config_integration.py`
- `tests/integration/test_monitor_state_integration.py`
- `tests/ccbot/handlers/test_interactive_ui.py`
- `tests/ccbot/handlers/test_response_builder.py`
- `tests/ccbot/handlers/test_status_polling.py`

---

## Рекомендация по мержу

### Стратегия: cherry-pick из malovlab в malovnik

Изменения в malovlab чистые и модульные. Весь WS-функционал изолирован в 3 новых файлах + минимальные точки интеграции в существующих модулях.

### Порядок мержа:

1. **Скопировать 3 новых файла:**
   - `src/ccbot/ws_bridge.py`
   - `src/ccbot/ws_protocol.py`
   - `src/ccbot/terminal_stream.py`

2. **Применить изменения в существующих файлах:**
   - `config.py` — добавить CCBOT_WS_TOKEN в SENSITIVE_ENV_VARS + 4 ws_* параметра
   - `session_monitor.py` — заменить single callback на list callbacks
   - `main.py` — добавить `_setup_logging()`, режим `web`, флаг `--with-web`
   - `bot.py` — добавить 9 строк запуска WS bridge в конец `create_bot()`
   - `hook.py` — добавить `_update_hook_path()` и расширить `_install_hook()`

3. **Добавить зависимости:**
   - `websockets` — в pyproject.toml dependencies
   - `aiofiles` — в pyproject.toml dependencies

4. **НЕ терять из malovnik:**
   - `tests/ccbot/test_new_features.py`
   - `[dependency-groups]` секция в pyproject.toml

### Оценка рисков:

| Изменение | Риск | Комментарий |
|-----------|------|-------------|
| 3 новых файла | Низкий | Полностью изолированы, не влияют на существующий код |
| session_monitor.py callbacks | Низкий | Backward-compatible, set_message_callback работает как раньше |
| config.py ws_* параметры | Низкий | Все optional, ws_enabled=False по умолчанию |
| main.py рефакторинг | Средний | Рефакторинг logging может конфликтовать с локальными изменениями |
| bot.py +9 строк | Низкий | Добавление в конец, без изменения существующей логики |
| hook.py update_path | Низкий | Расширение, не ломает существующее поведение |

### Заключение

Мерж безопасен. Все изменения в malovlab — это аддитивная функциональность (WebSocket bridge для веб-фронтенда), реализованная с правильной изоляцией. При `ws_enabled=False` (по умолчанию) поведение бота не меняется.
