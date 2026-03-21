# RM-09: Флаг --dangerously-skip-permissions

> **Приоритет:** FEATURE
> **Статус:** [x] ЗАВЕРШЁН (2026-03-21)
> **Зависимости:** RM-05 (рефакторинг завершён — знаем где create_window)
> **Оценка:** 1 сессия (быстрый чанк)

---

## Цель

При создании нового tmux окна Claude Code должен всегда запускаться с `--dangerously-skip-permissions`. Это bypass всех permission prompts, позволяя Claude работать полностью автономно.

---

## Подзадачи

### 1. Найти и изменить команду запуска Claude Code
- [ ] Через Serena: `find_symbol("create_window", include_body=true)` в `tmux_manager.py`
- [ ] Найти где формируется команда запуска: `config.claude_command` + аргументы
- [ ] Добавить `--dangerously-skip-permissions` к команде
- [ ] Убедиться что флаг добавляется и при `--resume` запуске

### 2. Сделать флаг конфигурируемым
- [ ] Добавить env var `CCBOT_DANGEROUS_MODE` (default: `true`) в `config.py`
- [ ] Если `false` — не добавлять флаг
- [ ] Обновить `.env.example` с новой переменной
- [ ] Docstring: объяснить зачем и когда отключать

### 3. Обновить документацию
- [ ] `doc/FULL_DOCUMENTATION.md` — новая env var + описание поведения
- [ ] `.claude/rules/architecture.md` — отметить в секции key decisions
- [ ] `doc/RALPH_LOOP_SUMMARY.md` — пометить как реализованное

### 4. Верификация
- [ ] Через Serena: `search_for_pattern("dangerously")` — только в нужных местах
- [ ] `ruff check src/` + `pyright src/ccbot/` — 0 errors
- [ ] Записать в Serena memory: `write_memory("rm09-dangerous-mode-added")`

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Выполнение | `superpowers:executing-plans` |
| Код | **Serena**: `find_symbol`, `replace_symbol_body` |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Добавление UI для toggle (это RM-10 — watcher)

---

## После завершения
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-09: add --dangerously-skip-permissions flag to Claude Code launch"`
- [ ] `git push`
- [ ] Обновить документацию
- [ ] `write_memory("rm09-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
