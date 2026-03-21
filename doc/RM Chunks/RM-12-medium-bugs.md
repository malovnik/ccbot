# RM-12: Medium-баги (M-2, M-4..M-9)

> **Приоритет:** MEDIUM
> **Статус:** [ ] Не начат
> **Зависимости:** RM-05 (рефакторинг завершён)
> **Оценка:** 1 сессия

---

## Цель

Исправить оставшиеся 6 medium-priority багов. M-1, M-3, M-10, M-11 уже исправлены в предыдущих ревизиях.

---

## Подзадачи

### 1. M-2: `telegram-bot-features.md` — устаревшая документация
- [ ] Прочитать `doc/telegram-bot-features.md`
- [ ] Исправить: ссылка на `/list` (не существует)
- [ ] Исправить: "10 commands registered" → актуальное количество
- [ ] Привести в соответствие с `doc/FULL_DOCUMENTATION.md`

### 2. M-4 + M-5: Import issues (monitor_state.py + markdown_v2.py)
- [ ] **M-4:** Через Serena: `find_symbol` в `monitor_state.py` — найти lazy import `atomic_write_json`
- [ ] Перенести на уровень модуля (как во всех остальных файлах)
- [ ] **M-5:** Через Serena: `search_for_pattern("_update_block")` в `markdown_v2.py`
- [ ] `from telegramify_markdown import _update_block` — private API
- [ ] Решение: закрепить версию `telegramify-markdown` в `pyproject.toml` с точной версией ИЛИ найти public API альтернативу
- [ ] Context7: проверить `telegramify-markdown` docs на public API

### 3. M-6 + M-7: Lossy path + Linux-only script
- [ ] **M-6:** Через Serena: `find_symbol("scan_projects", include_body=true)` в `session_monitor.py`
- [ ] `dir_name.replace("-", "/")` — заменяет ВСЕ дефисы
- [ ] Решение: использовать URL-safe encoding (`%2F` → `/`) или Base64 для directory names
- [ ] **M-7:** `scripts/restart.sh` — Linux-only (`pstree -a`, `grep -P`)
- [ ] Добавить macOS совместимость: `pgrep` + `grep -E` вместо `pstree -a` + `grep -P`
- [ ] ИЛИ: пометить как Linux-only в документации и создать `restart-macos.sh`

### 4. M-8 + M-9: CI + filesystem safety
- [ ] **M-8:** CI не измеряет coverage — добавить `--cov` в CI pipeline (если есть `.github/workflows/`)
- [ ] Если CI нет — пропустить, пометить как N/A
- [ ] **M-9:** `_IMAGES_DIR.mkdir()` на уровне модуля в bot.py (после рефакторинга — text_handler.py)
- [ ] Обернуть в `try/except OSError` → log warning (read-only filesystem)

### 5. Верификация
- [ ] `ruff check src/` + `pyright src/ccbot/` — 0 errors
- [ ] Записать в Serena memory: `write_memory("rm12-medium-bugs-fixed")`

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Выполнение | `superpowers:executing-plans` |
| Код | **Serena**: `find_symbol`, `replace_symbol_body`, `search_for_pattern` |
| telegramify docs | `context7-docs` |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Рефакторинг за пределами фиксов

---

## После завершения
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-12: fix medium bugs (M-2, M-4..M-9)"`
- [ ] `git push`
- [ ] Обновить `doc/AUDIT_REPORT.md` — все medium пометить как исправленные
- [ ] `write_memory("rm12-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
