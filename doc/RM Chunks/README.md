# CCBot Roadmap Chunks

> **Дата создания:** 2026-03-21
> **Статус:** ПЛАНИРОВАНИЕ — ожидает согласования
> **Общий принцип:** 1 чанк = 1 задача = вход для `superpowers:writing-plans`

---

## Правила выполнения

1. **Каждый чанк — начальный план** для составления детального плана через скилл `superpowers:writing-plans`
2. **Выполнение** — через `superpowers:executing-plans`
3. **После выполнения каждого чанка:**
   - `git commit` + `git push` (через `/push`)
   - Проверка функции в русской документации (`doc/FULL_DOCUMENTATION.md`)
   - Запись прогресса в Serena memory (`write_memory`)
   - Отметка статуса в чанке: `[ ] → [x]`
4. **Покрытие тестами ЗАПРЕЩЕНО** — пустая трата токенов
5. **Работа с кодом — ТОЛЬКО через Serena** (find_symbol, replace_symbol_body, etc.)
6. **Документация — через Context7** при работе с библиотеками

---

## Скиллы и плагины

| Скилл/Плагин | Когда использовать |
|---|---|
| `superpowers:writing-plans` | Перед началом каждого чанка — составить детальный план |
| `superpowers:executing-plans` | Выполнение плана |
| `superpowers:requesting-code-review` | После завершения чанка — ревью |
| `superpowers:verification-before-completion` | Перед коммитом — убедиться что всё работает |
| `code-review:code-review` | Ревью PR/изменений после крупных чанков |
| `simplify` | После написания нового кода — почистить |
| `debug` | При обнаружении багов в процессе |
| `context7-docs` | При работе с python-telegram-bot, libtmux, asyncio |
| **Serena** | ВСЯ работа с кодом: read/edit/search/refactor |
| **Sequential Thinking** | Сложные архитектурные решения в RM-00, RM-02..05 |

---

## Порядок выполнения

| # | Чанк | Приоритет | Зависит от |
|---|---|---|---|
| 00 | Архитектурный обзор и план масштабирования | ARCH | — |
| 01 | Critical баги (C-1..C-4) — крашат приложение | CRITICAL | 00 |
| 02 | Рефакторинг bot.py — command_handlers.py | REFACTOR | 01 |
| 03 | Рефакторинг bot.py — text_handler.py | REFACTOR | 02 |
| 04 | Рефакторинг bot.py — callback_handler.py | REFACTOR | 03 |
| 05 | Рефакторинг bot.py — session_lifecycle.py + финал | REFACTOR | 04 |
| 06 | High-баги: async/concurrency (H-1, H-2, H-6, H-7) | HIGH | 05 |
| 07 | High-баги: data integrity (H-3, H-4, H-5) | HIGH | 05 |
| 08 | High-баги: error handling (H-8, H-9, H-10) | HIGH | 05 |
| 09 | Флаг --dangerously-skip-permissions | FEATURE | 05 |
| 10 | Auto-approve watcher — встроить в ccbot | FEATURE | 09 |
| 11 | Мёрж WebSocket модулей из malovlab/ccbot | FEATURE | 05 |
| 12 | Medium-баги (M-2, M-4..M-9) | MEDIUM | 05 |
| 13 | Low-баги + code style (L-1..L-4) | LOW | 05 |
| 14 | Финальное обновление документации + ревью | DOCS | все |

---

## Статус

- [x] RM-00 — Архитектурный обзор
- [x] RM-01 — Critical баги
- [x] RM-02 — Рефакторинг: command_handlers
- [x] RM-03 — Рефакторинг: text_handler
- [x] RM-04 — Рефакторинг: callback_handler
- [x] RM-05 — Рефакторинг: session_lifecycle + финал
- [x] RM-06 — High: async/concurrency
- [x] RM-07 — High: data integrity
- [x] RM-08 — High: error handling
- [x] RM-09 — --dangerously-skip-permissions
- [ ] RM-10 — Auto-approve watcher
- [ ] RM-11 — WebSocket merge
- [ ] RM-12 — Medium баги
- [ ] RM-13 — Low баги + style
- [ ] RM-14 — Документация + финальное ревью
