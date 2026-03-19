# Развертывание CCBot

## Требования

| Компонент | Версия | Назначение |
|-----------|--------|-----------|
| Python | 3.12+ | Рантайм |
| uv | любая | Менеджер пакетов и виртуальных окружений |
| tmux | 3.0+ | Мультиплексор терминала для Claude Code сессий |
| Claude Code | актуальная | CLI Claude, запускается в tmux-окнах |

Опционально:

| Компонент | Назначение |
|-----------|-----------|
| Deepgram API key | Транскрипция голосовых сообщений |
| Шрифты (JetBrains Mono, Noto Sans CJK, Symbola) | Скриншоты терминала с Unicode |

## Установка

### Из исходников

```bash
git clone https://github.com/malovnik/ccbot.git
cd ccbot
uv sync
```

### Как uv tool (глобально)

```bash
uv tool install git+https://github.com/malovnik/ccbot.git
```

После установки команда `ccbot` будет доступна глобально.

### Проверка установки

```bash
uv run ccbot hook --install  # или просто ccbot hook --install при глобальной установке
```

Если установка прошла корректно, команда выведет сообщение об установке хука.

## Настройка .env

Создать директорию конфигурации и файл переменных:

```bash
mkdir -p ~/.ccbot
cp .env.example ~/.ccbot/.env
```

Отредактировать `~/.ccbot/.env`:

### Обязательные переменные

```bash
# Токен от @BotFather (Telegram)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# Telegram user ID (получить у @userinfobot)
# Несколько пользователей через запятую
ALLOWED_USERS=123456789
```

### tmux

```bash
# Имя tmux-сессии (по умолчанию: ccbot)
# Все окна Claude Code создаются внутри этой сессии
TMUX_SESSION_NAME=ccbot

# Команда запуска Claude Code в новых окнах (по умолчанию: claude)
# Для VPS без интерактивного терминала:
# CLAUDE_COMMAND=IS_SANDBOX=1 claude --dangerously-skip-permissions
CLAUDE_COMMAND=claude
```

### Polling

```bash
# Интервал опроса JSONL-файлов в секундах (по умолчанию: 2.0, минимум: 0.5)
# Меньше = быстрее реакция, больше нагрузка на IO
MONITOR_POLL_INTERVAL=2.0
```

### Голосовые сообщения

```bash
# API-ключ Deepgram (https://developers.deepgram.com)
# Без этого ключа голосовые сообщения игнорируются, остальное работает
DEEPGRAM_API_KEY=your_deepgram_key
```

### Безопасность

```bash
# Разрешенные корневые директории для браузера и файлов
# По умолчанию: ~ (домашняя директория)
# Ограничьте до своих проектов
CCBOT_ALLOWED_ROOTS=~/Documents/Dev,~/projects
```

### Вывод

```bash
# Фильтрация tool-спама (по умолчанию: true)
# При false в Telegram пойдут ВСЕ tool outputs включая результаты Bash
# Это может раскрыть секреты из переменных окружения
CCBOT_CLEAN_OUTPUT=true

# Эхо пользовательских сообщений (по умолчанию: false)
CCBOT_SHOW_USER_MESSAGES=false

# Показывать скрытые директории в браузере (по умолчанию: false)
CCBOT_SHOW_HIDDEN_DIRS=false
```

### WebSocket Bridge

```bash
# Включить WS-сервер для веб-фронтенда (по умолчанию: false)
CCBOT_WS_ENABLED=false

# Адрес и порт (по умолчанию: 127.0.0.1:8765)
CCBOT_WS_HOST=127.0.0.1
CCBOT_WS_PORT=8765

# Токен аутентификации (обязателен если WS включен на нелокальном адресе)
CCBOT_WS_TOKEN=your_secure_token
```

### Системные

```bash
# Директория конфигурации и state-файлов (по умолчанию: ~/.ccbot)
CCBOT_DIR=~/.ccbot
```

## Хук Claude Code

Хук SessionStart необходим для отслеживания сессий. Без него бот не знает, какие сессии мониторить.

### Автоматическая установка

```bash
ccbot hook --install
# или
uv run ccbot hook --install
```

Команда добавит хук в `~/.claude/settings.json`. Если хук уже установлен, команда обновит путь при необходимости.

### Ручная установка

Добавить в `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "ccbot hook",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Если ccbot установлен через `uv sync` (не глобально), указать полный путь:

```json
"command": "/path/to/ccbot/.venv/bin/ccbot hook"
```

### Проверка работы хука

После установки хука и запуска Claude Code в любом проекте файл `~/.ccbot/session_map.json` должен обновиться. Проверить:

```bash
cat ~/.ccbot/session_map.json
```

Ожидаемый формат:

```json
{
  "ccbot:@0": {
    "session_id": "uuid-xxx",
    "cwd": "/path/to/project",
    "window_name": "project"
  }
}
```

## Запуск

### Стандартный запуск

```bash
uv run ccbot
```

Бот запускает Telegram polling и мониторинг сессий. Для работы необходима запущенная tmux-сессия (создается автоматически при старте).

### С WebSocket Bridge

```bash
# Через переменную окружения
CCBOT_WS_ENABLED=true uv run ccbot

# Или через флаг
uv run ccbot --with-web
```

### Только WebSocket Bridge (без Telegram)

```bash
uv run ccbot web
```

### Запуск в tmux (рекомендуется для серверов)

```bash
# Создать tmux-сессию ccbot
tmux new-session -d -s ccbot

# Создать окно для самого бота
tmux new-window -t ccbot -n __main__

# Запустить бота в этом окне
tmux send-keys -t ccbot:__main__ "cd /path/to/ccbot && uv run ccbot" Enter
```

### Перезапуск

```bash
./scripts/restart.sh
```

Скрипт:
1. Находит процесс ccbot в tmux-окне `__main__`
2. Отправляет Ctrl-C, ожидает завершения (до 10 секунд)
3. При необходимости отправляет SIGTERM/SIGKILL
4. Запускает бот заново
5. Проверяет успешность запуска

### Настройка Telegram-группы

1. Создать группу в Telegram
2. Добавить бота в группу (с правами администратора)
3. Включить Topics в настройках группы (Settings -> Topics)
4. Написать в любой топик -- бот предложит выбрать директорию проекта

## WebSocket Bridge

### Назначение

WS bridge позволяет веб-фронтенду взаимодействовать с Claude Code сессиями параллельно с Telegram-ботом.

### Запуск

Три варианта:

```bash
# 1. Совместно с ботом (через .env)
# В .env: CCBOT_WS_ENABLED=true
uv run ccbot

# 2. Совместно с ботом (через флаг)
uv run ccbot --with-web

# 3. Standalone (без Telegram)
uv run ccbot web
```

### Аутентификация

- При `CCBOT_WS_HOST` = `127.0.0.1` / `localhost` / `::1` и отсутствии `CCBOT_WS_TOKEN` -- доступ без аутентификации
- В остальных случаях `CCBOT_WS_TOKEN` обязателен
- Клиент отправляет `{"type": "auth", "token": "..."}` в первые 30 секунд после подключения

### Лимиты

| Параметр | Значение |
|----------|---------|
| Max соединений | 20 |
| Rate limit | 60 msg/min на соединение |
| Max размер сообщения | 1 МБ |
| Max размер файла | 50 МБ |
| Auth timeout | 30 секунд |

## Troubleshooting

### Бот не отвечает на сообщения

1. Проверить, что `ALLOWED_USERS` содержит правильный Telegram ID
2. Убедиться, что группа имеет включенные Topics
3. Проверить логи: `cat ~/.ccbot/ccbot.log`

### Хук не работает

1. Проверить, что хук установлен: `cat ~/.claude/settings.json | grep ccbot`
2. Убедиться, что путь к `ccbot` корректный (особенно при установке через `uv sync`)
3. Запустить Claude Code в проекте и проверить `~/.ccbot/session_map.json`

### Сессии не отслеживаются

1. `session_map.json` должен содержать записи -- если пуст, хук не срабатывает
2. Проверить, что tmux-сессия имеет имя, совпадающее с `TMUX_SESSION_NAME` (по умолчанию `ccbot`)
3. Проверить `~/.ccbot/ccbot.log` на ошибки монитора

### Голосовые сообщения не транскрибируются

1. Убедиться, что `DEEPGRAM_API_KEY` задан в `.env`
2. Проверить валидность ключа: `curl -H "Authorization: Token YOUR_KEY" https://api.deepgram.com/v1/projects`

### Скриншоты отображаются без Unicode

Установить шрифты в `src/ccbot/fonts/`:
- JetBrains Mono (основной)
- Noto Sans CJK (CJK символы)
- Symbola (специальные символы)

При отсутствии шрифтов используется fallback Pillow -- функционально, но некрасиво.

### Rate limiting (429 ошибки)

Бот использует `AIORateLimiter(max_retries=5)` с глобальным лимитом 30 запросов в секунду. При 429 от Telegram все запросы приостанавливаются на указанный период. При перезапуске бота rate limiter bucket предзаполняется для предотвращения burst-а.

Если 429 возникают постоянно -- уменьшить `MONITOR_POLL_INTERVAL` или проверить количество активных сессий.

### tmux-окна не создаются

1. Убедиться, что tmux запущен: `tmux ls`
2. Проверить, что `CLAUDE_COMMAND` указывает на доступный бинарник: `which claude`
3. Проверить лог на ошибки создания окон

### Файлы не отправляются в Telegram

1. Проверить, что путь к файлу входит в `CCBOT_ALLOWED_ROOTS`
2. Убедиться, что расширение файла в whitelist (.md, .txt, .pdf, .docx и др.)
3. Файлы с sensitive-именами (.env, credentials, id_rsa) блокируются по дизайну

### Бот не запускается: "Error: TELEGRAM_BOT_TOKEN..."

Бот ищет `.env` в следующем порядке:
1. `.env` в текущей рабочей директории
2. `~/.ccbot/.env` (или `$CCBOT_DIR/.env`)

Убедиться, что файл существует и содержит `TELEGRAM_BOT_TOKEN` и `ALLOWED_USERS`.
