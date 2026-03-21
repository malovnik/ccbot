# RM-02: Рефакторинг bot.py — выделение command_handlers.py

> **Приоритет:** REFACTOR
> **Статус:** [ ] Не начат
> **Зависимости:** RM-01 (critical баги исправлены)
> **Оценка:** 1 сессия

---

## Цель

Первый шаг декомпозиции `bot.py` (1931 строка, god object). Выделить все command handlers в отдельный модуль `src/ccbot/handlers/command_handlers.py`. Цель — каждый модуль < 300 строк.

---

## Подзадачи

### 1. Анализ извлекаемых функций через Serena
- [ ] `get_symbols_overview("src/ccbot/bot.py")` — полный список символов
- [ ] Выделить command functions: `start_command`, `history_command`, `screenshot_command`, `esc_command`, `unbind_command`, `usage_command`, `kill_command` (или то что реализовано в RM-01), `forward_command_handler`
- [ ] Для каждой: `find_referencing_symbols` — кто вызывает, какие зависимости
- [ ] Составить список imports которые уйдут в новый модуль

### 2. Создать `src/ccbot/handlers/command_handlers.py`
- [ ] Определить сигнатуры: все command handlers принимают `(update, context)` — стандарт PTB
- [ ] Выделить функции через `find_symbol(include_body=true)` → создать новый файл
- [ ] Импорты: `session_manager`, `tmux_manager`, `config`, message_sender helpers
- [ ] Docstring модуля: назначение, ответственность

### 3. Обновить bot.py — убрать перенесённый код
- [ ] `replace_symbol_body` или удалить символы из bot.py
- [ ] Добавить `from .handlers.command_handlers import ...`
- [ ] Проверить что `create_bot()` wiring не сломался: `CommandHandler("start", start_command)` etc.
- [ ] Убедиться что `__all__` или namespace не конфликтуют

### 4. Проверка через Serena + lint
- [ ] `find_referencing_symbols` для каждой перенесённой функции — всё подключено?
- [ ] `ruff check src/` + `ruff format src/` + `pyright src/ccbot/` — 0 errors
- [ ] Проверить: ни один import path не сломан
- [ ] Записать в Serena memory: `write_memory("rm02-command-handlers-extracted")`

---

## Архитектурное решение (из RM-00)

```
bot.py (wiring only, <300 lines)
  └── handlers/
        ├── command_handlers.py  ← ЭТОТ ЧАНК
        ├── text_handler.py      ← RM-03
        ├── callback_handler.py  ← RM-04
        ├── session_lifecycle.py ← RM-05
        ├── message_queue.py     (уже есть)
        ├── message_sender.py    (уже есть)
        ├── status_polling.py    (уже есть)
        ├── ...
```

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Выполнение | `superpowers:executing-plans` |
| Код | **Serena**: `get_symbols_overview`, `find_symbol`, `replace_symbol_body`, `insert_after_symbol` |
| Рефакторинг | `simplify` — после извлечения |
| Ревью | `superpowers:requesting-code-review` |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Изменение логики функций — только перемещение
- Добавление новых фич в процессе рефакторинга

---

## После завершения
- [ ] `wc -l src/ccbot/bot.py` — должно уменьшиться на ~400-500 строк
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-02: extract command_handlers.py from bot.py"`
- [ ] `git push`
- [ ] Обновить `doc/FULL_DOCUMENTATION.md` — новая структура модулей
- [ ] `write_memory("rm02-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
