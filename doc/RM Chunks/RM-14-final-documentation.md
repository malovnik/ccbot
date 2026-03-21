# RM-14: Финальное обновление документации + ревью

> **Приоритет:** DOCS (финальный чанк)
> **Статус:** [ ] Не начат
> **Зависимости:** ВСЕ предыдущие чанки (RM-00..RM-13)
> **Оценка:** 1 сессия

---

## Цель

Полное обновление всей документации после завершения рефакторинга и фиксов. Финальный code review всего проекта. Документация должна на 100% соответствовать коду.

---

## Подзадачи

### 1. Полная перезапись `doc/FULL_DOCUMENTATION.md`
- [ ] Через Serena: `get_symbols_overview` для КАЖДОГО модуля (включая новые)
- [ ] Обновить секцию "Архитектура" — новая структура после рефакторинга
- [ ] Обновить секцию "Модули" — добавить `command_handlers.py`, `text_handler.py`, `callback_handler.py`, `session_lifecycle.py`, `auto_approve.py`, `ws_bridge.py`, `ws_protocol.py`, `terminal_stream.py`
- [ ] Обновить секцию bot.py — теперь wiring-only (~250 строк)
- [ ] Обновить секцию "Фичи" — auto-approve watcher, dangerous mode
- [ ] Обновить секцию "Конфигурация" — новые env vars
- [ ] Перекрёстная проверка: каждая публичная функция в коде = упомянута в документации

### 2. Обновить `doc/AUDIT_REPORT.md`
- [ ] Каждая из 29 находок: пометить статус (ИСПРАВЛЕНО / НЕ АКТУАЛЬНО / ОТЛОЖЕНО)
- [ ] Обновить граф зависимостей — новая структура модулей
- [ ] Обновить таблицу синглтонов (если изменилась в RM-00)
- [ ] Добавить секцию "Выполнение рекомендаций"

### 3. Обновить `.claude/rules/`
- [ ] `architecture.md` — полностью переписать диаграмму
- [ ] `topic-architecture.md` — проверить актуальность
- [ ] `message-handling.md` — проверить актуальность
- [ ] Добавить `rules/websocket.md` если WS интеграция сложная

### 4. Финальный code review через superpowers
- [ ] `superpowers:requesting-code-review` — полный review всего проекта
- [ ] `code-review:code-review` — дополнительный review
- [ ] Скилл `simplify` — финальная чистка
- [ ] `ruff check src/` + `ruff format --check src/` + `pyright src/ccbot/` — всё PASS

### 5. Финализация
- [ ] Обновить `doc/RALPH_LOOP_SUMMARY.md` — все требования реализованы
- [ ] Обновить `doc/RM Chunks/README.md` — все чанки `[x]`
- [ ] Записать финальный статус в Serena memory: `write_memory("rm14-all-complete")`
- [ ] Финальный коммит и пуш

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Документация | **Serena**: `get_symbols_overview` для всех модулей |
| Code review | `superpowers:requesting-code-review` |
| Code review | `code-review:code-review` |
| Чистка | `simplify` |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Изменение кода (только документация) — кроме мелких находок из code review
- Добавление новых фич

---

## После завершения
- [ ] Вся документация актуальна и соответствует коду
- [ ] Все 29 аудит-находок обработаны
- [ ] `ruff check src/` — PASS
- [ ] `ruff format --check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-14: final documentation update and code review"`
- [ ] `git push`
- [ ] `write_memory("rm14-completed-all-roadmap-done")` в Serena
- [ ] Все чанки `[x]` в `README.md`
