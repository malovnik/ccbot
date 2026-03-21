# RM-06: High-баги — async/concurrency (H-1, H-2, H-6, H-7)

> **Приоритет:** HIGH
> **Статус:** [ ] Не начат
> **Зависимости:** RM-05 (рефакторинг завершён — знаем где что лежит)
> **Оценка:** 1 сессия

---

## Цель

Исправить 4 high-priority бага, связанных с async и concurrency. Все могут приводить к deadlock, race condition или зависанию.

---

## Подзадачи

### 1. H-1: Deprecated `asyncio.get_event_loop()` в session.py
**Файл:** `session.py` (после рефакторинга — проверить расположение)

- [ ] Через Serena: `search_for_pattern("get_event_loop")` — найти все вхождения
- [ ] Заменить `asyncio.get_event_loop()` на `asyncio.get_running_loop()`
- [ ] Проверить: нет ли других deprecated asyncio вызовов в проекте
- [ ] Context7: `asyncio` docs — подтвердить правильность замены

### 2. H-2: `queue.join()` без timeout в message handling
**Файл:** был `bot.py`, теперь вероятно `text_handler.py` или `message_queue.py`

- [ ] Через Serena: `search_for_pattern("queue.join")` или `search_for_pattern("await.*join")`
- [ ] Добавить `asyncio.wait_for(queue.join(), timeout=30.0)` с обработкой `TimeoutError`
- [ ] При timeout: логировать warning + продолжать (не крашить)
- [ ] Проверить: все ли queue operations имеют reasonable timeouts

### 3. H-6: Race condition в `list_sessions_for_directory`
**Файл:** `session.py`

- [ ] Через Serena: `find_symbol("list_sessions_for_directory", include_body=true)`
- [ ] `glob()` + `stat()` — файл может быть удалён между вызовами
- [ ] Обернуть `stat()` в try/except `FileNotFoundError` → пропустить файл
- [ ] Рассмотреть: `Path.iterdir()` с inline stat вместо отдельного вызова

### 4. H-7: `subprocess.run` без timeout в hook.py
**Файл:** `hook.py`

- [ ] Через Serena: `find_symbol("hook_main", include_body=true)` — найти subprocess.run
- [ ] Добавить `timeout=10` к subprocess.run вызовам
- [ ] Обработать `subprocess.TimeoutExpired` → log error + graceful exit
- [ ] Проверить все `subprocess.run` в проекте: `search_for_pattern("subprocess.run")`

### 5. Верификация
- [ ] `ruff check src/` + `pyright src/ccbot/` — 0 errors
- [ ] `search_for_pattern("get_event_loop")` — 0 результатов
- [ ] Записать в Serena memory: `write_memory("rm06-async-bugs-fixed")`

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Выполнение | `superpowers:executing-plans` |
| Код | **Serena**: `search_for_pattern`, `find_symbol`, `replace_symbol_body` |
| asyncio docs | `context7-docs` |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Изменение async architecture (только точечные фиксы)

---

## После завершения
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-06: fix async/concurrency bugs (H-1, H-2, H-6, H-7)"`
- [ ] `git push`
- [ ] Обновить `doc/AUDIT_REPORT.md` — пометить H-1, H-2, H-6, H-7 исправленными
- [ ] `write_memory("rm06-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
