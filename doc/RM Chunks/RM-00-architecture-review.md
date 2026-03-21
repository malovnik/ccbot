# RM-00: Архитектурный обзор и план масштабирования

> **Приоритет:** ARCH (блокирует всё остальное)
> **Статус:** [x] ЗАВЕРШЁН (2026-03-21)
> **Зависимости:** нет
> **Оценка:** 1 сессия

---

## Цель

Пересмотреть текущую архитектуру CCBot с прицелом на масштабирование. Заложить фундамент для: multi-user, WebSocket frontend, plugin system. Зафиксировать архитектурные решения ДО начала рефакторинга.

---

## Подзадачи

### 1. Полный аудит текущей архитектуры через Serena
- [x] `get_symbols_overview` для каждого из 16 core модулей + 9 handlers
- [x] Построить реальный граф зависимостей (imports → exports)
- [x] Сверить с `doc/AUDIT_REPORT.md` — граф зависимостей всё ещё актуален?
- [x] Записать находки в Serena memory: `write_memory("rm00-architecture-audit")`

### 2. Анализ синглтонов и DI
- [x] Проверить все 4 синглтона: `config`, `tmux_manager`, `session_manager`, `_client`
- [x] Оценить: нужен ли DI контейнер для масштабирования?
- [x] Оценить: нужна ли абстракция над tmux (для будущего docker/podman)?
- [x] Вердикт: оставить синглтоны или перейти на DI — с обоснованием

### 3. Карта state-файлов и data flow
- [x] Проверить все state files: `state.json`, `session_map.json`, `monitor_state.json`
- [x] Оценить: нужна ли миграция на SQLite для конкурентного доступа?
- [x] Проверить file locking: где есть, где нет, где нужен
- [x] Оценить race conditions при multi-window операциях

### 4. План масштабирования — зафиксировать решения
- [x] Написать `doc/ARCHITECTURE_DECISIONS.md` с ADR (Architecture Decision Records)
- [x] Решения: DI vs синглтоны, JSON vs SQLite, монолит vs микросервисы
- [x] Решения по рефакторингу bot.py: финальная структура модулей
- [x] Решения по WS интеграции: как ws_bridge встраивается в lifecycle

### 5. Обновить `.claude/rules/architecture.md`
- [x] Привести в соответствие с реальным состоянием кода
- [x] Добавить section про планируемые изменения (WS, watcher)
- [x] Записать в Serena memory: `write_memory("rm00-architecture-decisions")`

---

## Скиллы и инструменты

| Этап | Скилл/Инструмент |
|---|---|
| Планирование | `superpowers:writing-plans` |
| Выполнение | `superpowers:executing-plans` |
| Архитектурные решения | `Sequential Thinking` (MCP) |
| Код | **Serena**: `get_symbols_overview`, `find_symbol`, `find_referencing_symbols` |
| Библиотеки | `context7-docs` для libtmux, python-telegram-bot |
| Финализация | `superpowers:verification-before-completion` |

---

## Запрещено
- Покрытие тестами
- Изменение кода (только анализ + документы)
- Преждевременная оптимизация

---

## После завершения
- [x] `git commit -m "RM-00: architecture review and scaling plan"`
- [ ] `git push`
- [x] Обновить `doc/FULL_DOCUMENTATION.md` — секция архитектуры
- [x] `write_memory("rm00-completed")` в Serena
- [x] Отметить `[x]` в `README.md`
