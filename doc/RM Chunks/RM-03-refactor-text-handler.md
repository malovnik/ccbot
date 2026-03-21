# RM-03: Рефакторинг bot.py — выделение text_handler.py

> **Приоритет:** REFACTOR
> **Статус:** [x] ЗАВЕРШЁН (2026-03-21)
> **Зависимости:** RM-02 (command_handlers извлечены)
> **Оценка:** 1 сессия

---

## Цель

Выделить основной routing сообщений (text, photo, voice) из `bot.py` в `src/ccbot/handlers/text_handler.py`. Это ядро бота — самая сложная часть рефакторинга.

---

## Подзадачи

### 1. Анализ text/media handler цепочки
- [ ] Через Serena: `find_symbol("text_handler", include_body=true)` в bot.py
- [ ] `find_symbol("handle_new_message", include_body=true)` — основной routing
- [ ] `find_symbol("photo_handler", include_body=true)` — обработка фото
- [ ] `find_symbol("voice_handler", include_body=true)` — голосовые
- [ ] `find_symbol("unsupported_content_handler", include_body=true)` — стикеры и пр.
- [ ] Маппинг зависимостей: кто из них вызывает кого

### 2. Создать `src/ccbot/handlers/text_handler.py`
- [ ] Перенести: `text_handler`, `handle_new_message`, `photo_handler`, `voice_handler`, `unsupported_content_handler`
- [ ] Перенести вспомогательные приватные функции (если есть)
- [ ] Определить API контракт: что экспортирует модуль для bot.py wiring
- [ ] Docstring: описание ответственности, flow диаграмма

### 3. Обработка зависимостей
- [ ] `send_to_window` — остаётся в session_manager или переносим?
- [ ] `_IMAGES_DIR` и photo cleanup — переместить в text_handler (M-9 фикс в RM-12)
- [ ] `transcribe_voice` — уже отдельный модуль, просто import
- [ ] Inline keyboard builders (directory browser trigger) — callback в bot.py или здесь?

### 4. Верификация
- [ ] `find_referencing_symbols` для каждой перенесённой функции
- [ ] `ruff check src/` + `pyright src/ccbot/` — 0 errors
- [ ] Проверить message flow: текст → routing → send_to_window → всё работает
- [ ] Записать в Serena memory: `write_memory("rm03-text-handler-extracted")`

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Выполнение | `superpowers:executing-plans` |
| Сложная логика | `Sequential Thinking` — routing decision tree |
| Код | **Serena**: полный набор |
| Ревью | `superpowers:requesting-code-review` |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Изменение логики routing (только перемещение)
- Оптимизация message handling (это отдельная задача)

---

## После завершения
- [ ] `wc -l src/ccbot/bot.py` — ещё -400-600 строк
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-03: extract text_handler.py from bot.py"`
- [ ] `git push`
- [ ] Обновить `doc/FULL_DOCUMENTATION.md`
- [ ] `write_memory("rm03-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
