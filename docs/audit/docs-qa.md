# QA проверка документации

> Дата: 2026-03-20
> Проверенные файлы: README_RU.md, docs/DEPLOYMENT.md, docs/FEATURES.md, docs/ARCHITECTURE.md
> Против кода: src/ccbot/bot.py, src/ccbot/config.py, .env.example, pyproject.toml

---

## Несоответствия

### [README_RU.md:Polling] Значение по умолчанию MONITOR_POLL_INTERVAL
**Документация говорит:** `MONITOR_POLL_INTERVAL` по умолчанию `3.0`
**Код на самом деле:** `config.py` строка 100 — `float(os.getenv("MONITOR_POLL_INTERVAL", "2.0"))`, значение по умолчанию `2.0`
**Рекомендация:** Исправить документацию на `2.0` или обновить .env.example

### [.env.example:Polling] Значение по умолчанию MONITOR_POLL_INTERVAL
**Документация говорит:** `# Monitor polling interval in seconds (default: 3.0, minimum: 0.5)`
**Код на самом деле:** default = `2.0` (config.py строка 100)
**Рекомендация:** Исправить комментарий на `default: 2.0`

### [docs/DEPLOYMENT.md:Polling] Значение по умолчанию MONITOR_POLL_INTERVAL
**Документация говорит:** `Интервал опроса JSONL-файлов в секундах (по умолчанию: 3.0, минимум: 0.5)`
**Код на самом деле:** default = `2.0`
**Рекомендация:** Исправить на `2.0`

### [README_RU.md:Конфигурация] Отсутствуют переменные окружения из config.py
**Документация говорит:** Документированы 18 переменных
**Код на самом деле:** config.py содержит дополнительные переменные, не документированные ни в README, ни в .env.example:
- `CCBOT_IDLE_REMINDER_SECONDS` (default: 120) — таймаут idle reminder
- `CCBOT_AUTO_RESTART` (default: true) — автоперезапуск Claude при крашах
- `CCBOT_FILE_RETENTION_DAYS` (default: 7) — время хранения скачанных файлов
- `CCBOT_LONG_RESPONSE_THRESHOLD` (default: 6000) — порог длинных ответов
- `CCBOT_INPUT_BATCH_SECONDS` (default: 1.5) — группировка быстрых сообщений
- `CCBOT_CLAUDE_PROJECTS_PATH` — кастомный путь к проектам Claude
- `CLAUDE_CONFIG_DIR` — альтернативный путь к конфигу Claude
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` — legacy, в SENSITIVE_ENV_VARS
**Рекомендация:** Добавить все переменные в README_RU.md и .env.example (хотя бы как закомментированные)

### [docs/ARCHITECTURE.md:config.py] Список SENSITIVE_ENV_VARS неполный
**Документация говорит:** 6 переменных скрабятся: `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`, `CLAUDE_API_KEY`, `CCBOT_WS_TOKEN`
**Код на самом деле:** SENSITIVE_ENV_VARS в config.py содержит: `TELEGRAM_BOT_TOKEN`, `ALLOWED_USERS`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `DEEPGRAM_API_KEY`, `CCBOT_WS_TOKEN` — нет `ANTHROPIC_API_KEY` и `CLAUDE_API_KEY`, зато есть `ALLOWED_USERS` и `OPENAI_BASE_URL`
**Рекомендация:** Обновить список в docs/ARCHITECTURE.md до фактического содержимого SENSITIVE_ENV_VARS

### [docs/FEATURES.md:Длинные ответы] Порог длинных ответов
**Документация говорит:** "Ответы длиннее 3000 символов" отправляются как превью + файл
**Код на самом деле:** config.py использует `CCBOT_LONG_RESPONSE_THRESHOLD` с default `6000`. Значение 3000 используется в response_builder.py для пагинации, но порог "превью + файл" = 6000
**Рекомендация:** Исправить на `6000` или указать оба порога (3000 для пагинации, 6000 для файла)

### [README_RU.md:Возможности] Количество реакций
**Документация говорит:** "Реакции на сообщения бота транслируются как фидбек Claude (19 маппингов)"
**Код на самом деле:** docs/FEATURES.md перечисляет ровно 19 реакций — OK, но стоит сверить с кодом при изменениях
**Рекомендация:** Соответствует (на момент проверки)

### [pyproject.toml:readme] Ссылка на README.md
**Документация говорит:** `readme = "README.md"` в pyproject.toml
**Код на самом деле:** Файл `README.md` существует в корне, но основная документация в `README_RU.md`. Нужно проверить, что README.md актуален или является ссылкой/алиасом
**Рекомендация:** Проверить содержимое README.md на актуальность

### [docs/DEPLOYMENT.md:WS Auth] Токен "обязателен если WS включен на нелокальном адресе"
**Документация говорит:** `.env.example` пишет "required if WS enabled", а DEPLOYMENT.md пишет "обязателен если WS включен на нелокальном адресе"
**Код на самом деле:** README_RU.md пишет "обязателен при включенном WS" — расхождение между тремя источниками
**Рекомендация:** Унифицировать формулировку. Фактически: localhost bypass позволяет без токена, но .env.example вводит в заблуждение

---

## Подтверждённая корректность

### Команды бота
- 12 CommandHandler в bot.py: `/start`, `/help`, `/history`, `/screenshot`, `/esc`, `/unbind`, `/kill`, `/restart`, `/usage`, `/health`, `/summary`, `/sessions` — все 12 документированы в README_RU.md: OK
- Проксируемые команды (`/clear`, `/compact`, `/cost`, `/model`, `/memory`) документированы как пересылаемые в Claude Code: OK

### Обязательные переменные
- `TELEGRAM_BOT_TOKEN` и `ALLOWED_USERS` — обязательны и в config.py (ValueError при отсутствии), и в документации, и в .env.example: OK

### Опциональные переменные (документированные)
- `TMUX_SESSION_NAME` (default: `ccbot`): OK
- `CLAUDE_COMMAND` (default: `claude`): OK
- `DEEPGRAM_API_KEY`: OK
- `CCBOT_ALLOWED_ROOTS` (default: `~`): OK
- `CCBOT_CLEAN_OUTPUT` (default: `true`): OK
- `CCBOT_SHOW_USER_MESSAGES` (default: `false`): OK
- `CCBOT_SHOW_HIDDEN_DIRS` (default: `false`): OK
- `CCBOT_WS_ENABLED` (default: `false`): OK
- `CCBOT_WS_HOST` (default: `127.0.0.1`): OK
- `CCBOT_WS_PORT` (default: `8765`): OK
- `CCBOT_WS_TOKEN`: OK
- `CCBOT_DIR` (default: `~/.ccbot`): OK

### Ссылки на файлы
- `LICENSE` — файл существует в корне: OK
- `scripts/restart.sh` — файл существует: OK
- `.env.example` — файл существует: OK

### Архитектура модулей
- Все перечисленные модули в docs/ARCHITECTURE.md существуют в коде: OK
- `_ensure_formatted()` дублируется в `message_queue.py` и `message_sender.py` — указано в docs/FEATURES.md как известная проблема: OK

### Quick Start
- `git clone` + `uv sync` — корректный синтаксис: OK
- `uv run ccbot hook --install` — entry point `ccbot = "ccbot.main:main"` в pyproject.toml: OK
- `uv run ccbot` — корректный запуск: OK

### pyproject.toml
- Python >= 3.12 соответствует docs/DEPLOYMENT.md (Python 3.12+): OK
- Зависимости в pyproject.toml соответствуют упоминаниям в ARCHITECTURE.md: OK
