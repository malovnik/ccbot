# RM-01: Critical баги (C-1..C-4) — крашат приложение

> **Приоритет:** CRITICAL
> **Статус:** [ ] Не начат
> **Зависимости:** RM-00 (архитектурные решения)
> **Оценка:** 1 сессия

---

## Цель

Исправить 4 критических бага, которые крашат приложение при запуске или в runtime. Каждый — потенциальный краш без recovery.

---

## Подзадачи

### 1. C-1: `/kill` команда — фантом
**Файл:** `bot.py` (menu registration + отсутствие handler)

- [ ] Через Serena: `find_symbol("kill")` — найти все упоминания
- [ ] Решить: реализовать `/kill` (kill tmux window + unbind) ИЛИ удалить из меню
- [ ] Если реализуем: `kill_command()` → confirm → `tmux_manager.kill_window()` → `session_manager.unbind_thread()` → cleanup
- [ ] Если удаляем: убрать из `_register_commands()` и `BotCommand` списка
- [ ] Обновить документацию: `doc/FULL_DOCUMENTATION.md` — убрать пометку "ФАНТОМ"

### 2. C-2: `config.py:130` — крах при импорте без env vars
**Файл:** `config.py`

- [ ] Через Serena: `find_symbol("Config/__init__")` с `include_body=true`
- [ ] Заменить `config = Config()` на module-level на lazy init: `_config: Config | None = None` + `def get_config() -> Config`
- [ ] ИЛИ: обернуть в try/except с понятным сообщением об ошибке
- [ ] Решение зависит от RM-00 (DI vs синглтон) — зафиксировать в ADR
- [ ] Проверить все `from .config import config` — если lazy init, обновить импорты

### 3. C-3: `session.py:893` — крах при `OSError` на `state.json`
**Файл:** `session.py`

- [ ] Через Serena: `find_symbol("SessionManager/_load_state")` с `include_body=true`
- [ ] Добавить `except OSError as e:` → log warning + создать пустой state
- [ ] Проверить: `_save_state()` тоже обработан на OSError?
- [ ] Проверить аналогичные паттерны в `monitor_state.py` и `session_map` loading

### 4. C-4: `screenshot.py:170` — `ValueError` от ANSI кодов
**Файл:** `screenshot.py`

- [ ] Через Serena: `find_symbol("_parse_ansi_line")` с `include_body=true`
- [ ] Обернуть `int(c)` в try/except ValueError → пропустить малформатный код
- [ ] Проверить: есть ли другие места с `int()` парсингом ANSI?
- [ ] Убедиться что вся цепочка `screenshot_command → text_to_image → _parse_ansi_line` обрабатывает exceptions

### 5. Верификация всех исправлений
- [ ] Через Serena: `find_referencing_symbols` для каждого изменённого метода
- [ ] Убедиться что исправления backward-compatible
- [ ] Запустить `ruff check src/` + `ruff format src/` + `pyright src/ccbot/`
- [ ] Записать в Serena memory: `write_memory("rm01-critical-bugs-fixed")`

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Выполнение | `superpowers:executing-plans` |
| Отладка (если нужна) | `debug` |
| Код | **Serena**: `find_symbol`, `replace_symbol_body`, `find_referencing_symbols` |
| Чистка | `simplify` — после всех фиксов |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Рефакторинг за пределами фикса (это RM-02..05)
- Изменение публичных API без обновления всех потребителей

---

## После завершения
- [ ] `ruff check src/` — PASS
- [ ] `pyright src/ccbot/` — 0 errors
- [ ] `git commit -m "RM-01: fix 4 critical bugs (C-1..C-4)"`
- [ ] `git push`
- [ ] Обновить `doc/FULL_DOCUMENTATION.md` + `doc/AUDIT_REPORT.md` (пометить исправленными)
- [ ] `write_memory("rm01-completed")` в Serena
- [ ] Отметить `[x]` в `README.md`
