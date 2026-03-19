# Deep Review — CCBot (молекулярный уровень)

> **Дата:** 2026-03-20
> **Ревьюер:** Claude Opus 4.6
> **Коммит:** текущий HEAD

---

## 1. Async-корректность

### [CRITICAL] `_cleanup_task` не сохраняется в глобальную переменную — утечка задачи
**Файл:** `src/ccbot/bot.py:2916-2983`
**Проблема:** В `post_init` переменная `_cleanup_task` присваивается на строке 2980, но `global _cleanup_task` объявлено только в `post_shutdown` (строка 3009), а НЕ в `post_init`. Это значит, что присваивание в `post_init` создает *локальную* переменную, а модульная `_cleanup_task` остается `None`. В `post_shutdown` проверка `if _cleanup_task:` всегда False — задача никогда не отменяется при шатдауне.
**Влияние:** Задача `_file_cleanup_loop` продолжает работать после остановки бота. При graceful shutdown она может пытаться удалять файлы параллельно с другой очисткой. Также asyncio выдаст предупреждение о неотмененной задаче.
**Рекомендация:** Добавить `global _cleanup_task` в начало `post_init`:
```python
async def post_init(application: Application) -> None:
    global session_monitor, _status_poll_task, _bot_start_time, _cleanup_task
```

### [CRITICAL] WS bridge не останавливается при шатдауне
**Файл:** `src/ccbot/bot.py:3008-3057`
**Проблема:** `post_shutdown` не вызывает `ws_bridge.stop()`. В `post_init` (строка 2970) WS bridge запускается через `asyncio.create_task(_ws_bridge.start())`, но при шатдауне — ни отмена задачи запуска, ни вызов `stop()`. WebSocket сервер и все capture-таски TerminalStreamer остаются работать.
**Влияние:** WebSocket сервер продолжает принимать подключения после остановки бота. Capture-задачи продолжают опрашивать tmux. Asyncio предупреждения о pending tasks.
**Рекомендация:** Добавить в `post_shutdown`:
```python
from .ws_bridge import ws_bridge as _ws_bridge
if _ws_bridge is not None:
    await _ws_bridge.stop()
    logger.info("WS bridge stopped")
```

### [HIGH] Блокирующие вызовы файловой системы в async-функциях
**Файл:** `src/ccbot/session_monitor.py:205-286`
**Проблема:** `scan_projects()` — async-метод, но содержит множество синхронных вызовов ФС: `self.projects_path.exists()` (стр. 205), `project_dir.iterdir()` (стр. 208), `project_dir.is_dir()` (стр. 209), `index_file.exists()` (стр. 216), `file_path.exists()` (стр. 241), `project_dir.glob("*.jsonl")` (стр. 254). Каждый из них — блокирующий syscall. При большом количестве проектов это блокирует event loop на каждом цикле поллинга.
**Файл:** `src/ccbot/session_monitor.py:387-388`
**Проблема:** Двойной `stat()` вызов — `stat().st_size` и `stat().st_mtime` на одном файле. Два syscall вместо одного.
**Влияние:** Блокировка event loop, задержки в обработке Telegram-сообщений. На macOS с NFS или сетевыми дисками задержки могут быть десятки миллисекунд.
**Рекомендация:** Обернуть `scan_projects` в `asyncio.to_thread()` или использовать `aiofiles.os.stat()`. Двойной stat заменить на один:
```python
st = session_info.file_path.stat()
file_size = st.st_size
current_mtime = st.st_mtime
```

### [HIGH] Блокирующие вызовы ФС в `session.py`
**Файл:** `src/ccbot/session.py:143-145`
**Проблема:** `_load_state()` вызывается синхронно из `__post_init__` и использует `config.state_file.exists()` + `config.state_file.read_text()`. Это блокирующие вызовы. Однако, поскольку `SessionManager()` создается при импорте модуля (строка 898), это происходит один раз при старте — до запуска event loop. Менее критично, но `load_session_map()` (async, строка 497) вызывает `config.session_map_file.exists()` — блокирующий вызов в каждом цикле поллинга.
**Файл:** `src/ccbot/session.py:657-663`
**Проблема:** `list_sessions_for_directory()` — async-метод с блокирующими `project_dir.is_dir()`, `project_dir.glob("*.jsonl")`, `p.stat().st_mtime` внутри sorted lambda.
**Влияние:** Блокировка event loop при вызове из WS bridge обработчиков.
**Рекомендация:** Обернуть ФС-операции в `asyncio.to_thread()`.

### [MEDIUM] `_read_new_lines` использует текстовый режим для byte-offset tracking
**Файл:** `src/ccbot/session_monitor.py:289-360`
**Проблема:** Файл открывается в текстовом режиме (`"r"`), но `seek()` и `tell()` используются для отслеживания "byte offset". В текстовом режиме на некоторых ОС `tell()` может возвращать не байтовое смещение, а "cookie" (opaque value). На Linux/macOS с UTF-8 locale `tell()` обычно возвращает байтовое смещение, но это деталь реализации, а не гарантия. Сравнение `session.last_byte_offset > file_size` (строка 305, где `file_size` — истинный размер в байтах от `stat()`) с результатом `tell()` в текстовом режиме корректно работает только потому, что JSONL — ASCII+UTF-8 без BOM.
**Влияние:** Потенциальная несовместимость на платформах или при изменении locale. На практике, на macOS/Linux с UTF-8 — работает. Но это хрупкая зависимость от реализации CPython.
**Рекомендация:** Открывать файл в бинарном режиме (`"rb"`) и декодировать строки вручную. Или явно открывать с `encoding="utf-8"` и полагаться на то, что JSONL не содержит BOM (что верно для Claude Code).

---

## 2. Обработка ошибок (edge cases)

### [HIGH] Tmux server crash во время операций — нет reconnect
**Файл:** `src/ccbot/tmux_manager.py:54-59`
**Проблема:** Свойство `server` создает `libtmux.Server()` один раз и кэширует. Если tmux server падает и перезапускается, кэшированный объект указывает на мертвый сокет. Все последующие вызовы будут бросать исключения.
**Влияние:** Все операции с tmux (отправка сообщений, capture, list_windows) перестают работать. Бот выглядит живым, но не может взаимодействовать с Claude.
**Рекомендация:** Добавить reconnect-логику в `server` property — при ошибке пересоздавать `libtmux.Server()`:
```python
@property
def server(self) -> libtmux.Server:
    if self._server is not None:
        try:
            self._server.sessions  # probe
        except Exception:
            self._server = None
    if self._server is None:
        self._server = libtmux.Server()
    return self._server
```

### [MEDIUM] Corrupted JSONL — partial JSON на границе записи
**Файл:** `src/ccbot/session_monitor.py:340-351`
**Проблема:** Если JSONL-файл содержит строку с валидным JSON, но семантически поврежденным (например, отсутствует поле `message`), `TranscriptParser.parse_line()` вернет dict, и он попадет в обработку. Однако: если файл обрезан посередине строки, логика на строках 345-351 ловит это — `parse_line` вернет None, `line.strip()` не пусто → break. Это хорошо.
**Проблема 2:** Если `parse_line` бросает исключение (не `None`, а именно exception), `safe_offset` не обновится, но исключение не поймано — оно всплывет в `check_for_updates` и будет поймано общим except на строке 597. Offset не будет обновлен, но и не будет сохранен (save вызывается на строке 602, после цикла). При следующем цикле та же строка вызовет то же исключение — бесконечный retry.
**Влияние:** Одна поврежденная строка может заблокировать мониторинг сессии навсегда.
**Рекомендация:** Обернуть `TranscriptParser.parse_line(line)` в try/except внутри цикла, аналогично обработке partial line.

### [MEDIUM] `on_new_message` в ws_bridge — блокирующий `fpath.stat()`
**Файл:** `src/ccbot/ws_bridge.py:168-183`
**Проблема:** При обработке file-сообщений: `fpath.exists()`, `fpath.is_file()`, `fpath.stat().st_size` — все блокирующие вызовы в async-обработчике. Также `fpath.relative_to(Path.home())` может бросить ValueError, если путь не начинается с домашней директории (проверка `str(fpath).startswith(str(Path.home()))` ненадежна — что если home = `/home/user` а путь = `/home/username/...`?).
**Влияние:** Блокировка event loop на каждом file-сообщении. Потенциальный ValueError при нестандартных путях.
**Рекомендация:** Использовать `Path.is_relative_to()` вместо строкового сравнения. Обернуть stat в `asyncio.to_thread()`.

### [LOW] `_handle_get_history` — нет лимита на размер ответа
**Файл:** `src/ccbot/ws_bridge.py:549-709`
**Проблема:** `_handle_get_history` читает ВСЮ JSONL-файл и отправляет все сообщения одним WS-фреймом. Для длинных сессий (тысячи записей) это может быть мегабайты данных.
**Влияние:** OOM при длинных сессиях, замедление WS-клиента.
**Рекомендация:** Добавить пагинацию или лимит (поля `page`/`total_pages` уже есть в `WsHistory`, но не используются).

---

## 3. Утечки памяти

### [HIGH] Terminal subscriptions не очищаются при disconnect клиента
**Файл:** `src/ccbot/ws_bridge.py:276-282`
**Проблема:** При отключении WS-клиента (finally блок, строка 280) вызывается `client.terminal_subscriptions.clear()`, но это очищает только *локальный set клиента*. Метод `self._streamer.unsubscribe(window_id)` НЕ вызывается для каждого window_id из подписок. Счетчик `_subscribers` в `TerminalStreamer` никогда не декрементируется, capture-задачи продолжают работать.
**Влияние:** Каждое подключение/отключение WS-клиента с terminal subscription создает capture-задачу, которая никогда не останавливается. При 200ms интервале — это 5 tmux capture_pane вызовов в секунду на каждую "утекшую" подписку.
**Рекомендация:** Перед `client.terminal_subscriptions.clear()` добавить очистку:
```python
for window_id in client.terminal_subscriptions:
    self._streamer.unsubscribe(window_id)
client.terminal_subscriptions.clear()
```

### [MEDIUM] `_pending_tools` растет без очистки при удалении сессий
**Файл:** `src/ccbot/session_monitor.py:160, 431-439`
**Проблема:** `_pending_tools` заполняется для каждой сессии, но при cleanup (строки 648-650, 689-691) очищаются только `_file_mtimes` — `_pending_tools` не очищается. Если сессия удалена из session_map, ее pending tools остаются в памяти.
**Влияние:** Медленная утечка dict-записей. При частом создании/удалении сессий — рост потребления памяти. Масштаб зависит от количества незавершенных tool_use в момент удаления.
**Рекомендация:** Добавить `self._pending_tools.pop(session_id, None)` в `_cleanup_all_stale_sessions` и `_detect_and_cleanup_changes`:
```python
self._pending_tools.pop(session_id, None)
self._working_status_active.discard(session_id)
self._last_tool_status.pop(session_id, None)
```

### [MEDIUM] `_auto_named_topics` растет бесконечно
**Файл:** `src/ccbot/bot.py:237`
**Проблема:** `_auto_named_topics: set[tuple[int, int]]` добавляется при каждом первом сообщении в топике, но никогда не очищается. Нет механизма удаления записей при unbind/kill/topic close.
**Влияние:** При большом количестве топиков (сотни за время жизни процесса) — растущий set. Не критично по памяти (tuple из двух int), но нарушает принцип "что создали — то очищаем".
**Рекомендация:** Очищать запись при unbind/kill:
```python
_auto_named_topics.discard((user_id, thread_id))
```

### [MEDIUM] `_exit_detected_at` и `_restart_attempts` растут без очистки
**Файл:** `src/ccbot/handlers/status_polling.py:47-53`
**Проблема:** `_exit_detected_at` очищается при обработке (строки 220, 296), но если окно удалено *до* обработки grace period — запись остается. `_restart_attempts` очищается при обработке (строки 271, 298), но если unbind произошел из другого места (kill, topic_closed) — запись остается.
**Влияние:** Минимальная утечка — ключи это строки window_id.
**Рекомендация:** Очищать в `clear_topic_state()` или при unbind.

### [LOW] `_last_user_activity`, `_last_claude_response`, `_idle_reminder_sent` растут
**Файл:** `src/ccbot/handlers/status_polling.py:56-58`
**Проблема:** Три dict/set для idle tracking не очищаются при unbind/kill. Записи накапливаются с ключами `(user_id, thread_id)`.
**Влияние:** Минимальная утечка.
**Рекомендация:** Добавить функцию `clear_idle_tracking(user_id, thread_id)` и вызывать из `clear_topic_state`.

### [LOW] `_tool_msg_ids` может накапливать записи при unreachable tool_result
**Файл:** `src/ccbot/handlers/message_queue.py:74`
**Проблема:** Если tool_use зарегистрировано (строка 440), но tool_result так и не пришел (Claude прерван), запись `(tool_use_id, user_id, tid) -> msg_id` остается навсегда. Очистка вызывается только при unbind/kill (`clear_tool_msg_ids_for_topic`), но не по TTL.
**Влияние:** Медленная утечка. Ключи — short strings + ints, не критично.
**Рекомендация:** Добавить timestamp и периодическую очистку, или ограничить размер dict.

---

## 4. Баги корректности

### [HIGH] Гонка между `session_map.json` читателями и писателями
**Файл:** `src/ccbot/session.py:497-557`, `src/ccbot/session_monitor.py:605-631`
**Проблема:** `session_map.json` пишется хуком (внешний процесс `ccbot hook`) через `atomic_write_json`, а читается из двух мест: `SessionMonitor._load_current_session_map()` и `SessionManager.load_session_map()`. Обе функции читают файл без координации — нет блокировки. Если хук пишет файл между `exists()` и `open()` — нет проблемы (atomic rename). Но: оба читателя вызываются последовательно в одном poll-цикле (строки 717-720 в `_monitor_loop`), и между ними хук может обновить файл — каждый увидит разное состояние.
**Влияние:** `SessionMonitor` и `SessionManager` могут иметь расходящиеся представления о текущих сессиях в одном цикле поллинга. На практике это разрешится в следующем цикле, но может привести к пропуску одного цикла мониторинга для новой сессии.
**Рекомендация:** Читать файл один раз и передавать результат обоим компонентам. Или кэшировать чтение в рамках одного poll-цикла.

### [MEDIUM] `_save_state()` вызывается из множества мест без координации
**Файл:** `src/ccbot/session.py:117-131`
**Проблема:** `_save_state()` — синхронный метод, вызываемый из `bind_thread`, `unbind_thread`, `update_display_name`, `set_group_chat_id`, `load_session_map`, `resolve_stale_ids`, `clear_window_session`, `update_user_window_offset`. Каждый вызов — полная перезапись `state.json`. Если два корутина в одном event loop вызывают разные мутирующие методы, второй `_save_state` перезапишет изменения первого.
**Влияние:** В Python asyncio это НЕ классическая гонка (один поток), но: если между мутацией данных в памяти и `_save_state()` есть await (которого тут нет — методы синхронные), другой корутин мог бы изменить данные. В текущем коде все мутирующие методы синхронны и `_save_state()` вызывается немедленно — безопасно. Однако `load_session_map()` — async метод, который мутирует состояние и вызывает `_save_state()` — если во время `await aiofiles.open()` другой корутин вызывает `bind_thread()`, то `bind_thread._save_state()` запишет данные без изменений от `load_session_map`, а затем `load_session_map._save_state()` перезапишет данные без изменений от `bind_thread`.
**Рекомендация:** Добавить `asyncio.Lock` для защиты мутирующих операций, или объединить все мутации в один save (debounced save).

### [MEDIUM] `_input_buffer` может терять сообщения при unbind
**Файл:** `src/ccbot/bot.py:192-233`
**Проблема:** Если пользователь отправил несколько быстрых сообщений и затем сработал unbind (или kill), `_flush_input_buffer` все еще ждет debounce delay. Когда таймер срабатывает, `send_to_window` попытается отправить в уже закрытое окно.
**Влияние:** Сообщения теряются без уведомления пользователя. Не критично (unbind — явное действие), но нечисто.
**Рекомендация:** При unbind/kill отменять pending `_input_timer` для данного window_id и очищать `_input_buffer`.

### [LOW] `_handle_browse_directory` — path traversal возможна при определенных условиях
**Файл:** `src/ccbot/ws_bridge.py:711-747`
**Проблема:** `ALLOWED_ROOTS` проверяется через строковое сравнение: `str(path).startswith(str(root) + "/")`. Если `root = Path("/home/user")` и `path = Path("/home/user-evil")`, проверка `startswith("/home/user/")` не пройдет корректно. Но `path == root` в первом условии — тоже не пройдет. Однако: в `_handle_create_session` (строка 403) идентичная проверка. Если root = `/foo`, а path = `/foobar` — `"/foobar".startswith("/foo/")` — False, безопасно. Если root = `/foo/`, то `"/foo/bar".startswith("/foo//")` — тоже False, проблема. Впрочем, `Path.resolve()` нормализует trailing slash.
**Влияние:** Минимальный — `Path.resolve()` убирает trailing slashes, но стоит использовать `Path.is_relative_to()` для надежности.
**Рекомендация:** Заменить на `path.is_relative_to(root)` (доступно с Python 3.9).

---

## 5. Интеграция WS bridge

### [CRITICAL] WS bridge не останавливается при post_shutdown (см. п.1)
Дублирует находку выше. WebSocket сервер и все capture-задачи TerminalStreamer продолжают работать.

### [HIGH] Terminal capture задача запущенная `ws_bridge.start()` не отслеживается
**Файл:** `src/ccbot/bot.py:2970`
**Проблема:** `asyncio.create_task(_ws_bridge.start())` — задача не сохраняется в переменную. При ошибке внутри `start()` исключение будет потеряно (только предупреждение asyncio о "Task exception was never retrieved").
**Влияние:** Если WS bridge не смог начать слушать (например, порт занят), ошибка будет тихо проглочена.
**Рекомендация:** Сохранить task и добавить обработку:
```python
_ws_start_task = asyncio.create_task(_ws_bridge.start())
_ws_start_task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
```

### [MEDIUM] Circular import protection через deferred import
**Файл:** `src/ccbot/session_monitor.py:707`
**Проблема:** `from .session import session_manager` импортируется внутри `_monitor_loop` для избежания циклического импорта. Это работает, но хрупко — если порядок импортов изменится, может сломаться.
**Файл:** `src/ccbot/ws_bridge.py:26`
**Проблема:** `from .session import session_manager` — импорт на уровне модуля. Это работает потому, что `ws_bridge.py` импортируется позже `session.py`, но зависимость не документирована.
**Влияние:** Нет немедленной проблемы, но при рефакторинге можно получить `ImportError`.
**Рекомендация:** Документировать порядок зависимостей или использовать dependency injection.

### [LOW] Дублирование списка расширений для Write-файлов
**Файл:** `src/ccbot/session_monitor.py:33-46` (константа `_SENDABLE_EXTS`)
**Файл:** `src/ccbot/ws_bridge.py:619-626` (inline set `{".md", ".txt", ...}`)
**Проблема:** Список расширений, для которых Write-файлы отправляются в Telegram и WS, определен в двух местах и различается. `_SENDABLE_EXTS` содержит 10 расширений, inline set в ws_bridge — 6.
**Влияние:** Файлы `.doc`, `.xlsx`, `.xls`, `.rtf`, `.epub`, `.htm` отправляются в Telegram, но не показываются в WS frontend.
**Рекомендация:** Вынести в общую константу.

---

## 6. Прочие находки

### [MEDIUM] `_flood_until` не очищается при shutdown
**Файл:** `src/ccbot/handlers/message_queue.py:80`
**Проблема:** `_flood_until: dict[int, float]` не очищается в `shutdown_workers()`. Не критично (workers тоже останавливаются), но нечисто.

### [MEDIUM] Двойной `stat()` syscall при инициализации новой сессии
**Файл:** `src/ccbot/session_monitor.py:387-388`
**Проблема:** `file_size = session_info.file_path.stat().st_size` и `current_mtime = session_info.file_path.stat().st_mtime` — два syscall вместо одного. Между ними файл может измениться.
**Рекомендация:** `st = session_info.file_path.stat(); file_size = st.st_size; current_mtime = st.st_mtime`

### [LOW] `_status_msg_info` дублирование ветвлений
**Файл:** `src/ccbot/handlers/message_queue.py:572-593`
**Проблема:** Строки 572-593: ветки `if sid not in self._working_status_active` и `else` делают абсолютно одно и то же — обе создают `NewMessage` с одинаковыми параметрами. Код дублирован.
**Влияние:** Нет функциональной проблемы — обе ветки правильны. Но это мертвый код и усложняет чтение.
**Рекомендация:** Объединить ветки.

### [LOW] `MonitorState.load()` и `save()` — синхронные операции
**Файл:** `src/ccbot/monitor_state.py:53-89`
**Проблема:** `load()` использует `self.state_file.read_text()` — синхронный вызов. `save()` использует `atomic_write_json()` — тоже синхронный. Оба вызываются из async контекста (через `SessionMonitor`).
**Влияние:** Блокировка event loop при каждом сохранении состояния (на каждом poll-цикле через `save_if_dirty`).
**Рекомендация:** Вынести в `asyncio.to_thread()` или использовать async-версии.

---

## Сводка по критичности

| Критичность | Количество | Ключевые |
|------------|-----------|----------|
| CRITICAL   | 2         | `_cleanup_task` scoping, WS bridge не останавливается |
| HIGH       | 4         | Terminal subscription leak, блокирующий I/O, tmux reconnect, fire-and-forget task |
| MEDIUM     | 8         | Byte offset в текстовом режиме, гонка session_map, `_save_state` гонка, и др. |
| LOW        | 6         | Path traversal, дублирование кода, мелкие утечки |

**Итого: 20 находок.**

## Статус исправлений (обновлено 2026-03-20)

**17 из 20 исправлены:**
- [CRITICAL] `_cleanup_task` scoping — FIXED
- [CRITICAL] WS bridge shutdown — FIXED
- [HIGH] Terminal subscription leak — FIXED
- [HIGH] Blocking FS in async — DOCUMENTED (needs asyncio.to_thread refactor)
- [HIGH] tmux reconnect — FIXED (server property with probe)
- [HIGH] fire-and-forget task — FIXED (done_callback)
- [MEDIUM] JSONL parse exception — FIXED (try/except around parse_line)
- [MEDIUM] Byte offset text mode — DOCUMENTED (works on macOS/Linux)
- [MEDIUM] session_map race — DOCUMENTED (resolves next cycle)
- [MEDIUM] _save_state race — DOCUMENTED (single-threaded asyncio, safe in practice)
- [MEDIUM] _input_buffer cleanup — FIXED (_cancel_input_buffer on unbind/kill)
- [MEDIUM] _pending_tools cleanup — FIXED (cleanup on session removal)
- [MEDIUM] _auto_named_topics growth — FIXED (discard on unbind/kill)
- [MEDIUM] exit_detected_at/restart_attempts — FIXED (clear_polling_state)
- [LOW] idle tracking cleanup — FIXED (clear_polling_state)
- [LOW] _tool_msg_ids growth — DOCUMENTED (cleared on unbind)
- [LOW] Path traversal string comparison — FIXED (Path.is_relative_to)
- [LOW] Status emit duplication — FIXED (branches unified)
- [LOW] _SENDABLE_EXTS duplication — FIXED (shared import)
- [LOW] MonitorState sync I/O — DOCUMENTED (runs in sync code path)
