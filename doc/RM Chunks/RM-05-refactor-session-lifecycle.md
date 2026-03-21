# RM-05: Рефакторинг bot.py — session_lifecycle.py + финализация

> **Приоритет:** REFACTOR
> **Статус:** [ ] Не начат
> **Зависимости:** RM-04 (callback_handler извлечён)
> **Оценка:** 1 сессия

---

## Цель

Финальный этап рефакторинга bot.py. Выделить session lifecycle logic в `src/ccbot/handlers/session_lifecycle.py`. После этого bot.py должен содержать ТОЛЬКО wiring: `create_bot()`, `post_init`, `post_shutdown`, регистрация handlers. Цель: bot.py < 300 строк.

---

## Подзадачи

### 1. Выделить session lifecycle функции
- [ ] Через Serena: `find_symbol("_create_and_bind_window", include_body=true)`
- [ ] `find_symbol("_capture_bash_output", include_body=true)`
- [ ] `find_symbol("topic_closed_handler", include_body=true)`
- [ ] `find_symbol("topic_edited_handler", include_body=true)`
- [ ] `find_symbol("_on_new_message", include_body=true)` — callback из SessionMonitor
- [ ] Определить что ещё осталось в bot.py кроме wiring

### 2. Создать `src/ccbot/handlers/session_lifecycle.py`
- [ ] Перенести: `_create_and_bind_window`, `_capture_bash_output`, `topic_closed_handler`, `topic_edited_handler`, `_on_new_message`
- [ ] Определить API: какие функции экспортируются для bot.py
- [ ] Docstring: жизненный цикл сессии — создание, мониторинг, закрытие

### 3. Финализация bot.py — только wiring
- [ ] bot.py должен содержать:
  - `create_bot()` — Application builder + handler registration
  - `post_init()` — startup logic
  - `post_shutdown()` — cleanup
  - Импорты из всех handler модулей
- [ ] `wc -l bot.py` < 300 строк — жёсткое требование
- [ ] Убедиться что все handler регистрации (`CommandHandler`, `MessageHandler`, `CallbackQueryHandler`) на месте

### 4. Полная проверка рефакторинга (RM-02..05)
- [ ] `ruff check src/` + `ruff format src/` + `pyright src/ccbot/` — 0 errors
- [ ] Через Serena: `get_symbols_overview` для bot.py — должны остаться только wiring functions
- [ ] Проверить: ни одна функция не потеряна, ни один import не сломан
- [ ] Скилл `superpowers:requesting-code-review` — полное ревью рефакторинга RM-02..05

### 5. Обновить все документы
- [ ] `doc/FULL_DOCUMENTATION.md` — полностью переписать секцию bot.py, добавить новые модули
- [ ] `.claude/rules/architecture.md` — обновить диаграмму
- [ ] `doc/AUDIT_REPORT.md` — пометить M-3 как решённый (bot.py больше не god object)
- [ ] Записать в Serena memory: `write_memory("rm05-refactoring-complete")`

---

## Целевая структура после RM-02..05

```
src/ccbot/
  bot.py                    (~250 lines) — wiring only
  handlers/
    command_handlers.py     (~300 lines) — /start, /history, /screenshot, /esc, /kill, /unbind, /usage, forward
    text_handler.py         (~400 lines) — text routing, photo, voice, unsupported content
    callback_handler.py     (~350 lines) — all inline keyboard callbacks
    session_lifecycle.py    (~300 lines) — create/bind window, topic close/edit, _on_new_message
    message_queue.py        (existing)
    message_sender.py       (existing)
    status_polling.py       (existing)
    response_builder.py     (existing)
    interactive_ui.py       (existing)
    directory_browser.py    (existing)
    cleanup.py              (existing)
    callback_data.py        (existing)
    history.py              (existing)
```

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Выполнение | `superpowers:executing-plans` |
| Код | **Serena**: полный набор |
| Ревью | `superpowers:requesting-code-review` (критично — полное ревью 4 чанков) |
| `code-review:code-review` | Дополнительное ревью |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Изменение логики (только перемещение + wiring)
- Оставлять bot.py > 300 строк

---

## После завершения
- [ ] `wc -l src/ccbot/bot.py` < 300
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-05: extract session_lifecycle.py, bot.py is now wiring-only (~250 lines)"`
- [ ] `git push`
- [ ] Обновить ВСЮ документацию
- [ ] `write_memory("rm05-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
