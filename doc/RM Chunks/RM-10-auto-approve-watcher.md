# RM-10: Auto-approve watcher — встроить в ccbot

> **Приоритет:** FEATURE
> **Статус:** [x] ЗАВЕРШЁН (2026-03-21)
> **Зависимости:** RM-09 (--dangerously-skip-permissions реализован)
> **Оценка:** 1-2 сессии

---

## Цель

Встроить функционал auto-approve watcher (сейчас внешний bash-скрипт `~/.claude/plugins/local/ralph-loop-local/scripts/watcher.sh`) непосредственно в ccbot. С toggle из Telegram per-window.

**Контекст:** `--dangerously-skip-permissions` (RM-09) покрывает обычные permission prompts, но НЕ покрывает `.claude/` self-edit prompt. Watcher нужен именно для этих специальных промптов.

---

## Подзадачи

### 1. Создать модуль `src/ccbot/auto_approve.py`
- [ ] Взять за основу логику из `watcher.sh` (45 строк — см. референс ниже)
- [ ] Реализовать как async class `AutoApproveWatcher`:
  - `start(window_id)` / `stop(window_id)` — per-window control
  - `_watch_loop(window_id)` — async loop с `tmux_manager.capture_pane()` + pattern matching
  - `add_pattern(name, regex, action)` — расширяемая система паттернов
  - `is_active(window_id)` → bool
- [ ] Паттерны из текущего watcher.sh:
  - `"allow Claude to edit its own settings"` → Down + Enter
  - `"authorize Claude to modify its config files"` → `y` + Enter
- [ ] Интервал polling: 2 секунды (как в watcher.sh)
- [ ] Cooldown: 3 секунды после действия (как в watcher.sh)

### 2. Интеграция с session lifecycle
- [ ] В `session_lifecycle.py`: при `_create_and_bind_window` — автостарт watcher если настроен
- [ ] При `topic_closed_handler` — автостоп watcher
- [ ] Состояние per-window: хранить в `state.json` или отдельном файле
- [ ] Default: включён для всех новых окон (конфигурируемо)

### 3. Telegram UI для управления
- [ ] Добавить команду `/watcher` или кнопку в interactive UI
- [ ] Toggle: ON/OFF per window
- [ ] Статус: показать какие окна с watcher
- [ ] Callback data: `CB_WATCHER_TOGGLE` = `wt:`
- [ ] Добавить в `callback_handler.py`

### 4. Конфигурация
- [ ] Env var: `CCBOT_AUTO_APPROVE` (default: `true`)
- [ ] Env var: `CCBOT_AUTO_APPROVE_PATTERNS` — JSON array дополнительных паттернов (опционально)
- [ ] Обновить `config.py` и `.env.example`

### 5. Верификация
- [ ] `ruff check src/` + `pyright src/ccbot/` — 0 errors
- [ ] Через Serena: `get_symbols_overview("src/ccbot/auto_approve.py")` — проверить структуру
- [ ] Записать в Serena memory: `write_memory("rm10-auto-approve-watcher")`

---

## Референс: текущий watcher.sh

```bash
# Паттерны:
# 1. "allow Claude to edit its own settings" → Down + Enter
# 2. "authorize Claude to modify its config files" → y + Enter
# Polling: 2 секунды
# Cooldown: 3 секунды после действия
# Scope: все panes в tmux сервере
```

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Архитектура | `Sequential Thinking` — async watcher design |
| Выполнение | `superpowers:executing-plans` |
| Код | **Serena**: полный набор |
| tmux API | `context7-docs` для libtmux |
| PTB API | `context7-docs` для python-telegram-bot |
| Ревью | `superpowers:requesting-code-review` |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Web UI toggle (это будущий WebSocket frontend)
- Усложнение: regex engine, plugin system для паттернов — достаточно простого list[tuple]

---

## После завершения
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-10: integrate auto-approve watcher into ccbot with TG toggle"`
- [ ] `git push`
- [ ] Обновить `doc/FULL_DOCUMENTATION.md` — новый модуль + TG команда
- [ ] Обновить `doc/RALPH_LOOP_SUMMARY.md` — пометить как реализованное
- [ ] `write_memory("rm10-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
