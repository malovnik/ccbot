# RM-13: Low-баги + code style (L-1..L-4)

> **Приоритет:** LOW
> **Статус:** [ ] Не начат
> **Зависимости:** RM-05 (рефакторинг завершён)
> **Оценка:** 0.5 сессии (быстрый чанк)

---

## Цель

Привести code style к единому стандарту. Мелкие фиксы которые улучшают читаемость и maintainability.

---

## Подзадачи

### 1. L-1: f-strings vs `%s` в logging — привести к единому стилю
- [ ] Через Serena: `search_for_pattern('logger\.(debug|info|warning|error).*f"')` — найти f-strings в logging
- [ ] Решить: `%s` (deferred evaluation, лучше для logging) ИЛИ f-strings (читаемость)
- [ ] Рекомендация аудита: `%s` предпочтительнее
- [ ] Заменить все f-strings в logging на `%s` формат
- [ ] Или наоборот — главное единообразие

### 2. L-2: `"noop"` hardcoded → CB_NOOP
- [ ] Через Serena: `search_for_pattern('"noop"')` — найти все вхождения
- [ ] Добавить `CB_NOOP = "noop"` в `handlers/callback_data.py`
- [ ] Заменить hardcoded строку на константу
- [ ] (Частично решено в RM-04 если callback_handler уже рефакторился)

### 3. L-3: `hook.py` — двойной import внутри функции
- [ ] Через Serena: `find_symbol` в `hook.py` — найти две `from .utils import ...`
- [ ] Объединить в один import на уровне функции (или вынести наверх если безопасно)
- [ ] Проверить: `hook.py` не импортирует `config.py` — это ограничение! utils может быть ok

### 4. L-4: `directory_browser.py` — лишняя пустая строка
- [ ] Через Serena: `get_symbols_overview("src/ccbot/handlers/directory_browser.py")`
- [ ] Убрать лишнюю пустую строку между imports (lines 22-24)
- [ ] `ruff format` может исправить автоматически

### 5. Финальный `ruff format` + проверка
- [ ] `ruff format src/ tests/` — полное форматирование
- [ ] `ruff check src/` — 0 errors
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] Записать в Serena memory: `write_memory("rm13-style-fixed")`

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Выполнение | `superpowers:executing-plans` (план простой — можно без writing-plans) |
| Код | **Serena**: `search_for_pattern`, `replace_symbol_body` |
| Чистка | `simplify` |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Рефакторинг логики (только стиль)

---

## После завершения
- [ ] `ruff check src/` — PASS
- [ ] `ruff format --check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-13: fix low priority bugs and unify code style (L-1..L-4)"`
- [ ] `git push`
- [ ] Обновить `doc/AUDIT_REPORT.md` — все low пометить как исправленные
- [ ] `write_memory("rm13-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
