# RM-07: High-баги — data integrity (H-3, H-4, H-5)

> **Приоритет:** HIGH
> **Статус:** [x] ЗАВЕРШЁН (2026-03-21)
> **Зависимости:** RM-05 (рефакторинг завершён)
> **Оценка:** 1 сессия

---

## Цель

Исправить 3 high-priority бага, связанных с целостностью данных: утечки файлов, двойной task_done, UnicodeDecodeError.

---

## Подзадачи

### 1. H-3: Photo files не чистятся при ошибке
**Файл:** после рефакторинга — `text_handler.py` (photo_handler)

- [ ] Через Serena: `find_symbol("photo_handler", include_body=true)`
- [ ] Найти где создаётся `~/.ccbot/images/<timestamp>.jpg`
- [ ] Добавить `try/finally` — cleanup файла при ошибке `send_to_window`
- [ ] Рассмотреть: использовать `tempfile.NamedTemporaryFile` вместо ручного management
- [ ] Проверить: нет ли других мест с file cleanup проблемами

### 2. H-4: `_merge_content_tasks` — fragile `task_done()`
**Файл:** `handlers/message_queue.py`

- [ ] Через Serena: `find_symbol("_merge_content_tasks", include_body=true)`
- [ ] Найти двойной `task_done()` компенсацию
- [ ] Решить: правильно ли считается количество task_done вызовов
- [ ] Если нужен двойной — документировать ПОЧЕМУ (комментарий)
- [ ] Если не нужен — убрать лишний вызов

### 3. H-5: `UnicodeDecodeError` в session_monitor
**Файл:** `session_monitor.py`

- [ ] Через Serena: `find_symbol("_read_new_lines", include_body=true)`
- [ ] Найти `aiofiles.open` вызовы — добавить `errors="replace"`
- [ ] Проверить ВСЕ `aiofiles.open` в проекте: `search_for_pattern("aiofiles.open")`
- [ ] Каждый open для JSONL файлов должен иметь `errors="replace"`

### 4. Верификация
- [ ] `ruff check src/` + `pyright src/ccbot/` — 0 errors
- [ ] `search_for_pattern("aiofiles.open")` — все с `errors="replace"` где нужно
- [ ] Записать в Serena memory: `write_memory("rm07-data-integrity-fixed")`

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Выполнение | `superpowers:executing-plans` |
| Код | **Serena**: `find_symbol`, `replace_symbol_body`, `search_for_pattern` |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Рефакторинг message_queue.py за пределами фикса

---

## После завершения
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-07: fix data integrity bugs (H-3, H-4, H-5)"`
- [ ] `git push`
- [ ] Обновить `doc/AUDIT_REPORT.md` — пометить H-3, H-4, H-5 исправленными
- [ ] `write_memory("rm07-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
