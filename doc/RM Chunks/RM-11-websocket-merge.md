# RM-11: Мёрж WebSocket модулей из malovlab/ccbot

> **Приоритет:** FEATURE
> **Статус:** [x] ЗАВЕРШЁН (2026-03-21)
> **Зависимости:** RM-05 (рефакторинг завершён)
> **Оценка:** 1-2 сессии

---

## Цель

Скопировать и адаптировать 3 WebSocket модуля из `malovlab/ccbot` (коммит `f6fff4a`) в основной репозиторий `malovnik/ccbot`. Интегрировать запуск WS-сервера в lifecycle приложения.

**Источник:** `/tmp/malovlab-ccbot/src/ccbot/` (уже клонирован)

---

## Подзадачи

### 1. Копирование и адаптация `ws_protocol.py` (302 строки)
- [ ] Скопировать `/tmp/malovlab-ccbot/src/ccbot/ws_protocol.py` → `src/ccbot/ws_protocol.py`
- [ ] Через Serena: `get_symbols_overview` — проверить все dataclass'ы
- [ ] Проверить совместимость типов: `Literal`, `dataclass`, `field` — всё есть в Python 3.12
- [ ] Проверить: `parse_client_message()` — безопасность (type validation, field validation)
- [ ] Адаптировать если нужно: импорты, naming conventions

### 2. Копирование и адаптация `terminal_stream.py` (100 строк)
- [ ] Скопировать `/tmp/malovlab-ccbot/src/ccbot/terminal_stream.py` → `src/ccbot/terminal_stream.py`
- [ ] Проверить: `from .tmux_manager import tmux_manager` — совместим с текущим API?
- [ ] `capture_pane(window_id, with_ansi=True)` — метод существует в текущем tmux_manager?
- [ ] Через Serena: `find_symbol("capture_pane")` в tmux_manager — сверить сигнатуру

### 3. Копирование и адаптация `ws_bridge.py` (665 строк) — основной модуль
- [ ] Скопировать `/tmp/malovlab-ccbot/src/ccbot/ws_bridge.py` → `src/ccbot/ws_bridge.py`
- [ ] Через Serena: `get_symbols_overview` — полная карта класса `WsBridge`
- [ ] Проверить все imports на совместимость с текущим кодом:
  - `session_manager` — API совпадает?
  - `tmux_manager` — API совпадает?
  - `config` — все нужные атрибуты есть?
- [ ] Адаптировать: `_handle_*` методы — вызывают текущие session/tmux API
- [ ] Добавить `websockets` в зависимости: `uv add websockets`

### 4. Интеграция запуска WS-сервера
- [ ] В `bot.py` (wiring) или `main.py`: добавить запуск WS-сервера при старте
- [ ] WS-сервер должен запускаться как asyncio task наряду с Telegram bot
- [ ] Shutdown: graceful stop WS-сервера при остановке приложения
- [ ] Env vars: `CCBOT_WS_PORT` (default: 8765), `CCBOT_WS_TOKEN` (для auth)
- [ ] Обновить `config.py` и `.env.example`

### 5. Верификация и документация
- [ ] `ruff check src/` + `pyright src/ccbot/` — 0 errors
- [ ] `uv sync` — websockets установлен
- [ ] Через Serena: `get_symbols_overview` для всех 3 новых файлов
- [ ] Обновить `doc/FULL_DOCUMENTATION.md` — 3 новых модуля
- [ ] Обновить `.claude/rules/architecture.md` — WS в диаграмме
- [ ] Обновить `doc/RALPH_LOOP_SUMMARY.md` — пометить как реализованное
- [ ] Записать в Serena memory: `write_memory("rm11-websocket-merged")`

---

## Модули для мёржа

| Файл | Строк | Описание |
|---|---|---|
| `ws_protocol.py` | 302 | 14 client→server + 13 server→client dataclass, parse/serialize |
| `terminal_stream.py` | 100 | Diff-based terminal capture 200ms, per-window subscriptions |
| `ws_bridge.py` | 665 | WS сервер: auth (HMAC), sessions, history, messages, keys, files, voice, terminal stream |

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Архитектура | `Sequential Thinking` — WS integration design |
| Выполнение | `superpowers:executing-plans` |
| Код | **Serena**: полный набор |
| websockets docs | `context7-docs` |
| Ревью | `superpowers:requesting-code-review` |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Написание web frontend (это второй этап)
- Изменение WS protocol (совместимость с будущим фронтом)

---

## После завершения
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-11: merge WebSocket modules from malovlab/ccbot"`
- [ ] `git push`
- [ ] Обновить всю документацию
- [ ] `write_memory("rm11-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
