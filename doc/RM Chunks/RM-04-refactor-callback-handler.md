# RM-04: Рефакторинг bot.py — выделение callback_handler.py

> **Приоритет:** REFACTOR
> **Статус:** [ ] Не начат
> **Зависимости:** RM-03 (text_handler извлечён)
> **Оценка:** 1 сессия

---

## Цель

Выделить обработку inline keyboard callbacks из `bot.py` в `src/ccbot/handlers/callback_handler.py`. Callback handler — огромная switch-case машина с десятками prefix-based routes.

---

## Подзадачи

### 1. Анализ callback routing
- [ ] Через Serena: `find_symbol("callback_handler", include_body=true)` в bot.py
- [ ] Составить список всех `CB_*` prefixes и их handlers:
  - `CB_DIR_*` → directory browser actions
  - `CB_WIN_*` → window picker actions
  - `CB_SESSION_*` → session picker actions
  - `CB_HISTORY_*` → history pagination
  - `CB_ASK_*` → interactive UI navigation
  - `CB_SCREENSHOT_*` → screenshot controls
  - `CB_KEYS_*` → key sending
- [ ] Для каждого route: `find_referencing_symbols` — внешние зависимости

### 2. Создать `src/ccbot/handlers/callback_handler.py`
- [ ] Перенести основную `callback_handler()` функцию
- [ ] Перенести все вспомогательные функции для callback routing
- [ ] Структура: один главный dispatcher + методы по категориям
- [ ] Import из существующих handler модулей: `directory_browser`, `interactive_ui`, `history`, `cleanup`

### 3. Рефакторинг callback dispatch
- [ ] Рассмотреть: dict-based dispatch вместо if/elif chain
- [ ] Каждая категория callbacks — отдельная async функция
- [ ] `answer_callback_query()` — убедиться что вызывается для КАЖДОГО callback (Telegram требование)
- [ ] L-2 фикс: заменить `"noop"` на `CB_NOOP` константу (из AUDIT_REPORT)

### 4. Верификация
- [ ] `find_referencing_symbols("callback_handler")` — bot.py wiring обновлён
- [ ] `ruff check src/` + `pyright src/ccbot/` — 0 errors
- [ ] Все inline keyboard callbacks корректно маршрутизируются
- [ ] Записать в Serena memory: `write_memory("rm04-callback-handler-extracted")`

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Выполнение | `superpowers:executing-plans` |
| Код | **Serena**: полный набор |
| Чистка | `simplify` — dict dispatch vs if/elif |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Изменение callback data format (это сломает существующие inline keyboards)
- Добавление новых callback types

---

## После завершения
- [ ] `wc -l src/ccbot/bot.py` — ещё -300-500 строк
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-04: extract callback_handler.py from bot.py"`
- [ ] `git push`
- [ ] Обновить `doc/FULL_DOCUMENTATION.md`
- [ ] `write_memory("rm04-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
