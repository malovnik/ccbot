# Ralph Loop — Итоговый отчёт по CCBot

> **Дата:** 2026-03-21
> **Итераций:** 6 из 20 (завершено по completion promise)

---

## Поиск и выбор репозитория

- **malovnik/ccbot** (70+ коммитов, активный) — победитель
- `malovlab/ccbot` — пустышка (1 коммит, 3 файла) — отброшен
- Организация malovlab

---

## Исследование (итерации 1-2)

3 параллельных агента прошерстили весь код:
- 16 core модулей (`src/ccbot/*.py`)
- 9 handler модулей (`src/ccbot/handlers/*.py`)
- Конфиг, документация, тесты, CI/CD

---

## Аудит (итерация 3)

4 параллельных агента-аудитора:
1. Импорты и зависимости
2. Data flow и состояние
3. Error handling
4. Фичи и конфиг

### Находки

| Приоритет | Кол-во | Примеры |
|-----------|--------|---------|
| CRITICAL | 4 | `/kill` — фантом (в меню есть, handler нет); config крашит при импорте без env; `session.py` — нет `OSError` handler; `screenshot.py` — `ValueError` от ANSI |
| HIGH | 10 | deprecated `get_event_loop()`, `queue.join()` без timeout, утечка фото-файлов, `UnicodeDecodeError` в мониторе |
| MEDIUM | 11 | `.env.example` — было 5 из 13 переменных (исправлено), CI без coverage, `restart.sh` Linux-only |
| LOW | 4 | f-strings vs %s в logging, стиль |

---

## Три ревизии (итерации 4-6)

### Ревизия 1/3 — Исправление документации
9 фактических ошибок исправлено:
- `/kill` помечен как ФАНТОМ
- `model_command()` удалён (не существует)
- bot.py: "~500 строк" исправлено на "~1930 строк"
- `topic_edited_handler` и `_capture_bash_output` добавлены в документацию
- `.env.example` обновлён: 5 → 13 переменных
- CC_COMMANDS добавлены в таблицу команд
- `_create_and_bind_window` добавлен в key functions

### Ревизия 2/3 — Перекрёстная проверка код vs документация
12 пропущенных публичных методов добавлено:
- `session.py` (+6): `get_window_for_thread()`, `get_display_name()`, `get_window_state()`, `clear_window_session()`, `update_display_name()`, `update_user_window_offset()`
- `tmux_manager.py` (+2): `get_session()`, `server` property
- `message_queue.py` (+4): `get_message_queue()`, `get_or_create_queue()`, `clear_status_msg_info()`, `clear_tool_msg_ids_for_topic()`

0 фактических ошибок найдено.

### Ревизия 3/3 — Финальная проверка
- 1 дубликат фичи убран (#30 и #40 — обе Topic Name Sync)
- 5 стейл-находок в аудите помечены как исправленные (M-1, M-3, M-10, M-11, рекомендации #6, #7)

---

## Артефакты

| Файл | Строк | Содержание |
|------|-------|------------|
| `doc/FULL_DOCUMENTATION.md` | 771 | Все 16 модулей, 9 handlers, 40 фич, все env vars, команды, state files |
| `doc/AUDIT_REPORT.md` | 203 | 29 находок с приоритетами, граф зависимостей, непротестированные пути |
| `RALPH_LOOP_LOG.md` | 216 | Полный лог всех 6 итераций |

---

---

## Требования к реализации

### Claude Code должен запускаться с `--dangerously-skip-permissions`

При создании нового окна tmux, Claude Code должен **всегда** запускаться с флагом `--dangerously-skip-permissions` (полный bypass всех permission prompts). Это убирает интерактивные подтверждения и позволяет Claude работать полностью автономно.

**Где менять:** `tmux_manager.py` → `create_window()` — добавить флаг в команду запуска Claude.

### Auto-approve watcher — встроить в ccbot

Сейчас на компе работает отдельный скрипт `~/.claude/plugins/local/ralph-loop-local/scripts/watcher.sh`, который каждые 2 сек сканирует все tmux panes и автоматом прожимает `.claude/` permission prompts (Down + Enter). Нужно:

1. **Встроить в ccbot** как встроенную фичу (не внешний скрипт)
2. **Toggle из Telegram** — команда или кнопка для вкл/выкл auto-approve per window
3. **Toggle из веб-фронта** — когда будет web UI
4. **Паттерны для авто-прожатия** (из текущего watcher.sh):
   - `"allow Claude to edit its own settings"` → Down + Enter
   - `"authorize Claude to modify its config files"` → `y` + Enter
5. **Расширяемость** — легко добавлять новые паттерны
6. **Per-window настройка** — можно включить для одних окон и выключить для других
7. **Совместимость с `--dangerously-skip-permissions`** — если флаг включён, watcher не нужен для обычных permission prompts, но `.claude/` self-edit prompt отдельный и bypass его не покрывает

**Референс:** `~/.claude/plugins/local/ralph-loop-local/scripts/watcher.sh` (45 строк)

### Смёрж WebSocket модулей из malovlab/ccbot

В репо `malovlab/ccbot` обнаружены 3 модуля которых нет в основном `malovnik/ccbot`:

| Файл | Строк | Описание |
|------|-------|----------|
| `ws_bridge.py` | 665 | WebSocket сервер: auth, сессии, история, сообщения, клавиши, файлы, голос, terminal stream |
| `ws_protocol.py` | 302 | Типизированный протокол: 14 client→server + 13 server→client dataclass |
| `terminal_stream.py` | 100 | Diff-based terminal capture каждые 200мс с подписками per-window |

**Действие:** Скопировать в `malovnik/ccbot`, адаптировать к текущей версии кода, добавить `websockets` в зависимости, интегрировать запуск WS-сервера в `bot.py`/`main.py`.

**Источник:** `https://github.com/malovlab/ccbot.git` — коммит `f6fff4a`

### Веб-фронтенд — ВТОРОЙ ЭТАП (не сейчас)

Фронтенд был написан, но потерян (не закоммичен). Разработка веб-UI — отдельный этап после стабилизации TG + WS бэкенда.

### Рефакторинг `bot.py` — 1930 строк в одном файле

`bot.py` — 1930 строк, god object. Нужна декомпозиция на логические модули:

- **command_handlers.py** — `/start`, `/history`, `/screenshot`, `/esc`, `/unbind`, `/usage`
- **text_handler.py** — основной routing сообщений (text, photo, voice)
- **callback_handler.py** — обработка inline keyboard callbacks (directory browser, window picker, session picker, interactive UI, history pagination)
- **session_lifecycle.py** — `_create_and_bind_window`, `_capture_bash_output`, topic close/edit
- **bot.py** — только `create_bot()`, `post_init`, `post_shutdown`, wiring

Цель: каждый файл < 300 строк, чёткая ответственность, тестируемость.

---

## Коммит

`8f079e7` — pushed to `origin/main`
