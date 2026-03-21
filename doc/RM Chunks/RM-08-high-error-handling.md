# RM-08: High-баги — error handling (H-8, H-9, H-10)

> **Приоритет:** HIGH
> **Статус:** [ ] Не начат
> **Зависимости:** RM-05 (рефакторинг завершён)
> **Оценка:** 1 сессия

---

## Цель

Исправить 3 high-priority бага, связанных с error handling: молчаливая потеря данных, inconsistent exception handling, утечка секретов.

---

## Подзадачи

### 1. H-8: `_capture_bash_output` — двойной silent `pass`
**Файл:** после рефакторинга — `session_lifecycle.py`

- [ ] Через Serena: `find_symbol("_capture_bash_output", include_body=true)`
- [ ] И MarkdownV2 edit, и plain-text fallback фейлят → вывод молча теряется
- [ ] Добавить fallback уровня 3: простой `send_message` без форматирования
- [ ] Логировать ошибку вместо `pass` — чтобы было видно что вывод потерялся
- [ ] Проверить аналогичные двойные-pass паттерны: `search_for_pattern("except.*pass")`

### 2. H-9: `safe_reply` re-raises, а `safe_send`/`safe_edit` — нет
**Файл:** `handlers/message_sender.py`

- [ ] Через Serena: `find_symbol("safe_reply", include_body=true)`
- [ ] `find_symbol("safe_send", include_body=true)` и `find_symbol("safe_edit", include_body=true)`
- [ ] Привести к единому поведению: все `safe_*` должны логировать, но НЕ re-raise
- [ ] Вызывающий код не ожидает exceptions от `safe_*` — re-raise ломает handlers

### 3. H-10: `_scrub_session_env` — `except Exception: pass` скрывает утечку секретов
**Файл:** `tmux_manager.py`

- [ ] Через Serena: `find_symbol("_scrub_session_env", include_body=true)`
- [ ] Заменить `except Exception: pass` на конкретные exceptions
- [ ] Если `unset_environment` фейлит не с "var not set" → log ERROR + предупредить о потенциальной утечке
- [ ] Проверить: TELEGRAM_BOT_TOKEN, OPENAI_API_KEY — все scrub'ятся?

### 4. Аудит всех `except.*pass` в проекте
- [ ] `search_for_pattern("except.*:.*pass")` — полный список
- [ ] Каждый `pass` — оценить: нужен ли logging вместо молчаливого проглатывания
- [ ] Заменить критические `pass` на `logger.warning/error`
- [ ] Записать в Serena memory: `write_memory("rm08-error-handling-fixed")`

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
- Добавление custom exception classes (over-engineering для текущего масштаба)

---

## После завершения
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-08: fix error handling bugs (H-8, H-9, H-10)"`
- [ ] `git push`
- [ ] Обновить `doc/AUDIT_REPORT.md` — пометить H-8, H-9, H-10 исправленными
- [ ] `write_memory("rm08-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
