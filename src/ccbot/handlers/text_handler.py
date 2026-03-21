"""Text, photo, and voice message handlers — core message routing.

Handles user messages arriving in Telegram topics:
  - text_handler: main routing — forwards text to Claude Code via tmux,
    triggers directory browser for unbound topics, detects interactive UIs.
  - photo_handler: downloads photo, forwards file path to Claude Code.
  - voice_handler: transcribes voice via OpenAI, forwards text.
  - handle_new_message: processes assistant responses from SessionMonitor,
    enqueues for delivery to Telegram.
  - _capture_bash_output: background task for ``!`` command output capture.
"""

import asyncio
import logging
import time
from pathlib import Path

from telegram import Bot, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from ..config import config
from ..markdown_v2 import convert_markdown
from ..session import session_manager
from ..session_monitor import NewMessage
from ..terminal_parser import extract_bash_output, is_interactive_ui
from ..tmux_manager import tmux_manager
from ..transcribe import transcribe_voice
from ..utils import ccbot_dir
from .command_handlers import _get_thread_id, is_user_allowed
from .directory_browser import (
    BROWSE_DIRS_KEY,
    BROWSE_PAGE_KEY,
    BROWSE_PATH_KEY,
    STATE_BROWSING_DIRECTORY,
    STATE_KEY,
    STATE_SELECTING_SESSION,
    STATE_SELECTING_WINDOW,
    UNBOUND_WINDOWS_KEY,
    build_directory_browser,
    build_window_picker,
    clear_browse_state,
    clear_session_picker_state,
    clear_window_picker_state,
)
from .interactive_ui import (
    INTERACTIVE_TOOL_NAMES,
    clear_interactive_mode,
    clear_interactive_msg,
    get_interactive_msg_id,
    get_interactive_window,
    handle_interactive_ui,
    set_interactive_mode,
)
from .message_queue import (
    clear_status_msg_info,
    enqueue_content_message,
    enqueue_status_update,
    get_message_queue,
)
from .message_sender import NO_LINK_PREVIEW, safe_reply, send_with_fallback
from .response_builder import build_response_parts

logger = logging.getLogger(__name__)

# --- Image directory for incoming photos ---
_IMAGES_DIR = ccbot_dir() / "images"
try:
    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)
except OSError as e:
    logger.warning("Cannot create images directory %s: %s", _IMAGES_DIR, e)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photos sent by the user: download and forward path to Claude Code."""
    user = update.effective_user
    if not user or not is_user_allowed(user.id):
        if update.message:
            await safe_reply(update.message, "You are not authorized to use this bot.")
        return

    if not update.message or not update.message.photo:
        return

    chat = update.message.chat
    thread_id = _get_thread_id(update)
    if chat.type in ("group", "supergroup") and thread_id is not None:
        session_manager.set_group_chat_id(user.id, thread_id, chat.id)

    # Must be in a named topic
    if thread_id is None:
        await safe_reply(
            update.message,
            "Please use a named topic. Create a new topic to start a session.",
        )
        return

    wid = session_manager.get_window_for_thread(user.id, thread_id)
    if wid is None:
        await safe_reply(
            update.message,
            "No session bound to this topic. Send a text message first to create one.",
        )
        return

    w = await tmux_manager.find_window_by_id(wid)
    if not w:
        display = session_manager.get_display_name(wid)
        session_manager.unbind_thread(user.id, thread_id)
        await safe_reply(
            update.message,
            f"Window '{display}' no longer exists. Binding removed.\n"
            "Send a message to start a new session.",
        )
        return

    # Download the highest-resolution photo
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()

    # Save to ~/.ccbot/images/<timestamp>_<file_unique_id>.jpg
    filename = f"{int(time.time())}_{photo.file_unique_id}.jpg"
    file_path = _IMAGES_DIR / filename
    await tg_file.download_to_drive(file_path)

    # Build the message to send to Claude Code
    caption = update.message.caption or ""
    if caption:
        text_to_send = f"{caption}\n\n(image attached: {file_path})"
    else:
        text_to_send = f"(image attached: {file_path})"

    await update.message.chat.send_action(ChatAction.TYPING)
    clear_status_msg_info(user.id, thread_id)

    success, message = await session_manager.send_to_window(wid, text_to_send)
    if not success:
        # Clean up downloaded file on send failure
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass
        await safe_reply(update.message, f"{message}")
        return

    # Confirm to user
    await safe_reply(update.message, "Image sent to Claude Code.")


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages: transcribe via OpenAI and forward text to Claude Code."""
    user = update.effective_user
    if not user or not is_user_allowed(user.id):
        if update.message:
            await safe_reply(update.message, "You are not authorized to use this bot.")
        return

    if not update.message or not update.message.voice:
        return

    if not config.deepgram_api_key and not config.openai_api_key:
        await safe_reply(
            update.message,
            "Voice transcription requires an API key.\n"
            "Set `DEEPGRAM_API_KEY` or `OPENAI_API_KEY` in your `.env` file.",
        )
        return

    chat = update.message.chat
    thread_id = _get_thread_id(update)
    if chat.type in ("group", "supergroup") and thread_id is not None:
        session_manager.set_group_chat_id(user.id, thread_id, chat.id)

    if thread_id is None:
        await safe_reply(
            update.message,
            "Please use a named topic. Create a new topic to start a session.",
        )
        return

    wid = session_manager.get_window_for_thread(user.id, thread_id)
    if wid is None:
        await safe_reply(
            update.message,
            "No session bound to this topic. Send a text message first to create one.",
        )
        return

    w = await tmux_manager.find_window_by_id(wid)
    if not w:
        display = session_manager.get_display_name(wid)
        session_manager.unbind_thread(user.id, thread_id)
        await safe_reply(
            update.message,
            f"Window '{display}' no longer exists. Binding removed.\n"
            "Send a message to start a new session.",
        )
        return

    # Download voice as in-memory bytes
    voice_file = await update.message.voice.get_file()
    ogg_data = bytes(await voice_file.download_as_bytearray())

    # Transcribe
    try:
        text = await transcribe_voice(ogg_data)
    except ValueError as e:
        await safe_reply(update.message, f"{e}")
        return
    except Exception as e:
        logger.error("Voice transcription failed: %s", e)
        await safe_reply(update.message, f"Transcription failed: {e}")
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    clear_status_msg_info(user.id, thread_id)

    success, message = await session_manager.send_to_window(wid, text)
    if not success:
        await safe_reply(update.message, f"{message}")
        return

    await safe_reply(update.message, f'"{text}"')


# Active bash capture tasks: (user_id, thread_id) -> asyncio.Task
_bash_capture_tasks: dict[tuple[int, int], asyncio.Task[None]] = {}


def _cancel_bash_capture(user_id: int, thread_id: int) -> None:
    """Cancel any running bash capture for this topic."""
    key = (user_id, thread_id)
    task = _bash_capture_tasks.pop(key, None)
    if task and not task.done():
        task.cancel()


async def _capture_bash_output(
    bot: Bot,
    user_id: int,
    thread_id: int,
    window_id: str,
    command: str,
) -> None:
    """Background task: capture ``!`` bash command output from tmux pane.

    Sends the first captured output as a new message, then edits it
    in-place as more output appears.  Stops after 30 s or when cancelled
    (e.g. user sends a new message, which pushes content down).
    """
    try:
        # Wait for the command to start producing output
        await asyncio.sleep(2.0)

        chat_id = session_manager.resolve_chat_id(user_id, thread_id)
        msg_id: int | None = None
        last_output: str = ""

        for _ in range(30):
            raw = await tmux_manager.capture_pane(window_id)
            if raw is None:
                return

            output = extract_bash_output(raw, command)
            if not output:
                await asyncio.sleep(1.0)
                continue

            # Skip edit if nothing changed
            if output == last_output:
                await asyncio.sleep(1.0)
                continue

            last_output = output

            # Truncate to fit Telegram's 4096-char limit
            if len(output) > 3800:
                output = "... " + output[-3800:]

            if msg_id is None:
                # First capture -- send a new message
                sent = await send_with_fallback(
                    bot,
                    chat_id,
                    output,
                    message_thread_id=thread_id,
                )
                if sent:
                    msg_id = sent.message_id
            else:
                # Subsequent captures -- edit in place
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=convert_markdown(output),
                        parse_mode="MarkdownV2",
                        link_preview_options=NO_LINK_PREVIEW,
                    )
                except Exception:
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=msg_id,
                            text=output,
                            link_preview_options=NO_LINK_PREVIEW,
                        )
                    except Exception as e:
                        logger.warning("Bash capture: failed to edit message: %s", e)

            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        return
    finally:
        _bash_capture_tasks.pop((user_id, thread_id), None)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_user_allowed(user.id):
        if update.message:
            await safe_reply(update.message, "You are not authorized to use this bot.")
        return

    if not update.message or not update.message.text:
        return

    thread_id = _get_thread_id(update)

    # Capture group chat_id for supergroup forum topic routing.
    # Required: Telegram Bot API needs group chat_id (not user_id) to send
    # messages with message_thread_id. Do NOT remove -- see session.py docs.
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        session_manager.set_group_chat_id(user.id, thread_id, chat.id)

    text = update.message.text

    # Ignore text in window picker mode (only for the same thread)
    if context.user_data and context.user_data.get(STATE_KEY) == STATE_SELECTING_WINDOW:
        pending_tid = context.user_data.get("_pending_thread_id")
        if pending_tid == thread_id:
            await safe_reply(
                update.message,
                "Please use the window picker above, or tap Cancel.",
            )
            return
        # Stale picker state from a different thread -- clear it
        clear_window_picker_state(context.user_data)
        context.user_data.pop("_pending_thread_id", None)
        context.user_data.pop("_pending_thread_text", None)

    # Ignore text in directory browsing mode (only for the same thread)
    if (
        context.user_data
        and context.user_data.get(STATE_KEY) == STATE_BROWSING_DIRECTORY
    ):
        pending_tid = context.user_data.get("_pending_thread_id")
        if pending_tid == thread_id:
            await safe_reply(
                update.message,
                "Please use the directory browser above, or tap Cancel.",
            )
            return
        # Stale browsing state from a different thread -- clear it
        clear_browse_state(context.user_data)
        context.user_data.pop("_pending_thread_id", None)
        context.user_data.pop("_pending_thread_text", None)

    # Ignore text in session picker mode (only for the same thread)
    if (
        context.user_data
        and context.user_data.get(STATE_KEY) == STATE_SELECTING_SESSION
    ):
        pending_tid = context.user_data.get("_pending_thread_id")
        if pending_tid == thread_id:
            await safe_reply(
                update.message,
                "Please use the session picker above, or tap Cancel.",
            )
            return
        # Stale picker state from a different thread -- clear it
        clear_session_picker_state(context.user_data)
        context.user_data.pop("_pending_thread_id", None)
        context.user_data.pop("_pending_thread_text", None)
        context.user_data.pop("_selected_path", None)

    # Must be in a named topic
    if thread_id is None:
        await safe_reply(
            update.message,
            "Please use a named topic. Create a new topic to start a session.",
        )
        return

    wid = session_manager.get_window_for_thread(user.id, thread_id)
    if wid is None:
        # Unbound topic -- check for unbound windows first
        all_windows = await tmux_manager.list_windows()
        bound_ids = {wid for _, _, wid in session_manager.iter_thread_bindings()}
        unbound = [
            (w.window_id, w.window_name, w.cwd)
            for w in all_windows
            if w.window_id not in bound_ids
        ]
        logger.debug(
            "Window picker check: all=%s, bound=%s, unbound=%s",
            [w.window_name for w in all_windows],
            bound_ids,
            [name for _, name, _ in unbound],
        )

        if unbound:
            # Show window picker
            logger.info(
                "Unbound topic: showing window picker (%d unbound windows, user=%d, thread=%d)",
                len(unbound),
                user.id,
                thread_id,
            )
            msg_text, keyboard, win_ids = build_window_picker(unbound)
            if context.user_data is not None:
                context.user_data[STATE_KEY] = STATE_SELECTING_WINDOW
                context.user_data[UNBOUND_WINDOWS_KEY] = win_ids
                context.user_data["_pending_thread_id"] = thread_id
                context.user_data["_pending_thread_text"] = text
            await safe_reply(update.message, msg_text, reply_markup=keyboard)
            return

        # No unbound windows -- show directory browser to create a new session
        logger.info(
            "Unbound topic: showing directory browser (user=%d, thread=%d)",
            user.id,
            thread_id,
        )
        start_path = str(config.browse_start_dir)
        msg_text, keyboard, subdirs = build_directory_browser(start_path)
        if context.user_data is not None:
            context.user_data[STATE_KEY] = STATE_BROWSING_DIRECTORY
            context.user_data[BROWSE_PATH_KEY] = start_path
            context.user_data[BROWSE_PAGE_KEY] = 0
            context.user_data[BROWSE_DIRS_KEY] = subdirs
            context.user_data["_pending_thread_id"] = thread_id
            context.user_data["_pending_thread_text"] = text
        await safe_reply(update.message, msg_text, reply_markup=keyboard)
        return

    # Bound topic -- forward to bound window
    w = await tmux_manager.find_window_by_id(wid)
    if not w:
        display = session_manager.get_display_name(wid)
        logger.info(
            "Stale binding: window %s gone, unbinding (user=%d, thread=%d)",
            display,
            user.id,
            thread_id,
        )
        session_manager.unbind_thread(user.id, thread_id)
        await safe_reply(
            update.message,
            f"Window '{display}' no longer exists. Binding removed.\n"
            "Send a message to start a new session.",
        )
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    await enqueue_status_update(context.bot, user.id, wid, None, thread_id=thread_id)

    # Cancel any running bash capture -- new message pushes pane content down
    _cancel_bash_capture(user.id, thread_id)

    # Check for pending interactive UI before sending text.
    # This catches UIs (permission prompts, etc.) that status polling might have missed.
    pane_text = await tmux_manager.capture_pane(w.window_id)
    if pane_text and is_interactive_ui(pane_text):
        # UI detected -- show it to user, then send text (acts as Enter)
        logger.info(
            "Detected pending interactive UI before sending text (user=%d, thread=%s)",
            user.id,
            thread_id,
        )
        await handle_interactive_ui(context.bot, user.id, wid, thread_id)
        # Small delay to let UI render in Telegram before text arrives
        await asyncio.sleep(0.3)

    success, message = await session_manager.send_to_window(wid, text)
    if not success:
        await safe_reply(update.message, f"{message}")
        return

    # Start background capture for ! bash command output
    if text.startswith("!") and len(text) > 1:
        bash_cmd = text[1:]  # strip leading "!"
        task = asyncio.create_task(
            _capture_bash_output(context.bot, user.id, thread_id, wid, bash_cmd)
        )
        _bash_capture_tasks[(user.id, thread_id)] = task

    # If in interactive mode, refresh the UI after sending text
    interactive_window = get_interactive_window(user.id, thread_id)
    if interactive_window and interactive_window == wid:
        await asyncio.sleep(0.2)
        await handle_interactive_ui(context.bot, user.id, wid, thread_id)


# --- Streaming response / notifications ---


async def handle_new_message(msg: NewMessage, bot: Bot) -> None:
    """Handle a new assistant message -- enqueue for sequential processing.

    Messages are queued per-user to ensure status messages always appear last.
    Routes via thread_bindings to deliver to the correct topic.
    """
    status = "complete" if msg.is_complete else "streaming"
    logger.info(
        f"handle_new_message [{status}]: session={msg.session_id}, "
        f"text_len={len(msg.text)}"
    )

    # Find users whose thread-bound window matches this session
    active_users = await session_manager.find_users_for_session(msg.session_id)

    if not active_users:
        logger.info(f"No active users for session {msg.session_id}")
        return

    for user_id, wid, thread_id in active_users:
        # Handle interactive tools specially - capture terminal and send UI
        if msg.tool_name in INTERACTIVE_TOOL_NAMES and msg.content_type == "tool_use":
            # Mark interactive mode BEFORE sleeping so polling skips this window
            set_interactive_mode(user_id, wid, thread_id)
            # Flush pending messages (e.g. plan content) before sending interactive UI
            queue = get_message_queue(user_id)
            if queue:
                try:
                    await asyncio.wait_for(queue.join(), timeout=30.0)
                except TimeoutError:
                    logger.warning("Queue flush timed out for user %d", user_id)
            # Wait briefly for Claude Code to render the question UI
            await asyncio.sleep(0.3)
            handled = await handle_interactive_ui(bot, user_id, wid, thread_id)
            if handled:
                # Update user's read offset
                session = await session_manager.resolve_session_for_window(wid)
                if session and session.file_path:
                    try:
                        file_size = Path(session.file_path).stat().st_size
                        session_manager.update_user_window_offset(
                            user_id, wid, file_size
                        )
                    except OSError:
                        pass
                continue  # Don't send the normal tool_use message
            else:
                # UI not rendered -- clear the early-set mode
                clear_interactive_mode(user_id, thread_id)

        # Any non-interactive message means the interaction is complete -- delete the UI message
        if get_interactive_msg_id(user_id, thread_id):
            await clear_interactive_msg(user_id, bot, thread_id)

        # Skip tool call notifications when CCBOT_SHOW_TOOL_CALLS=false
        if not config.show_tool_calls and msg.content_type in (
            "tool_use",
            "tool_result",
        ):
            continue

        parts = build_response_parts(
            msg.text,
            msg.is_complete,
            msg.content_type,
            msg.role,
        )

        if msg.is_complete:
            # Enqueue content message task
            # Note: tool_result editing is handled inside _process_content_task
            # to ensure sequential processing with tool_use message sending
            await enqueue_content_message(
                bot=bot,
                user_id=user_id,
                window_id=wid,
                parts=parts,
                tool_use_id=msg.tool_use_id,
                content_type=msg.content_type,
                text=msg.text,
                thread_id=thread_id,
                image_data=msg.image_data,
            )

            # Update user's read offset to current file position
            # This marks these messages as "read" for this user
            session = await session_manager.resolve_session_for_window(wid)
            if session and session.file_path:
                try:
                    file_size = Path(session.file_path).stat().st_size
                    session_manager.update_user_window_offset(user_id, wid, file_size)
                except OSError:
                    pass
