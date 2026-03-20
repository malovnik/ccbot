# Message Handling

## Message Queue Architecture

Per-user message queues + worker pattern for all send tasks:
- Messages are sent in receive order (FIFO)
- Status messages always follow content messages
- Multi-user concurrent processing without interference

**Message merging**: The worker automatically merges consecutive mergeable content messages on dequeue:
- Content messages for the same window can be merged (including text, thinking)
- tool_use breaks the merge chain and is sent separately (message ID recorded for later editing)
- tool_result breaks the merge chain and is edited into the tool_use message (preventing order confusion)
- Merging stops when combined length exceeds 3800 characters (to avoid pagination)

## Status Message Handling

**Conversion**: The status message is edited into the first content message, reducing message count:
- When a status message exists, the first content message updates it via edit
- Subsequent content messages are sent as new messages

**Polling**: Background task polls terminal status for all active windows at 3-second intervals (`STATUS_POLL_INTERVAL`). Send-layer rate limiting ensures flood control is not triggered.

**Deduplication**: The worker compares `last_text` when processing status updates; identical content skips the edit, reducing API calls.

## Rate Limiting

- `AIORateLimiter(max_retries=5)` on the Application (30/s global)
- On 429, AIORateLimiter pauses all concurrent requests (`_retry_after_event`) and retries after the ban
- On restart, the global bucket is pre-filled (`_level=max_rate`) to avoid burst against Telegram's persisted server-side counter
- Status polling interval: 3 seconds (skips enqueue when queue is non-empty)

## Performance Optimizations

**mtime cache**: The monitoring loop maintains an in-memory file mtime cache, skipping reads for unchanged files.

**Byte offset incremental reads**: Each tracked session records `last_byte_offset`, reading only new content. File truncation (offset > file_size) is detected and offset is auto-reset.

## Input Batching

Fast consecutive user messages are batched via `_enqueue_batched_input` with a configurable debounce timer (`CCBOT_INPUT_BATCH_SECONDS`, default 1.5s). Messages accumulate in `_input_buffer` until the timer fires, then all are sent as one combined prompt. Timer and buffer are cancelled on unbind/kill via `_cancel_input_buffer`.

## Topic Cleanup

`clear_topic_state()` in `handlers/cleanup.py` is the single cleanup entry point, called on unbind, kill, and topic close. It clears:
- Status message tracking (`_status_msg_info`)
- Tool message IDs (`_tool_msg_ids`)
- Interactive UI state
- Polling state (idle tracking, restart attempts) via `clear_polling_state`
- Pending thread state from `user_data`

Additionally, `_auto_named_topics` and `_input_buffer` are cleared directly in bot.py handlers.

## No Message Truncation

Historical messages (tool_use summaries, tool_result text, user/assistant messages) are always kept in full — no character-level truncation at the parsing layer. Long text is handled exclusively at the send layer: `split_message` splits by Telegram's 4096-character limit; real-time messages get `[1/N]` text suffixes, history pages get inline keyboard navigation.
