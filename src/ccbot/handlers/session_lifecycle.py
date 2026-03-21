"""Session lifecycle handlers — topic open/close/edit, window creation.

Manages the lifecycle of Claude Code sessions tied to Telegram topics:
  - topic_closed_handler: kills tmux window and cleans up state on topic close/delete
  - topic_edited_handler: syncs topic rename to tmux window name
  - _create_and_bind_window: creates a new tmux window, binds it to a topic,
    waits for SessionStart hook, and forwards pending text
"""

import logging

from telegram import CallbackQuery, Update, User
from telegram.ext import ContextTypes

from ..session import session_manager
from ..tmux_manager import tmux_manager
from .cleanup import clear_topic_state
from .command_handlers import _get_thread_id, is_user_allowed
from .message_sender import safe_edit, safe_send

logger = logging.getLogger(__name__)


async def topic_closed_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle topic closure — kill the associated tmux window and clean up state."""
    user = update.effective_user
    if not user or not is_user_allowed(user.id):
        return

    thread_id = _get_thread_id(update)
    if thread_id is None:
        return

    wid = session_manager.get_window_for_thread(user.id, thread_id)
    if wid:
        display = session_manager.get_display_name(wid)
        w = await tmux_manager.find_window_by_id(wid)
        if w:
            await tmux_manager.kill_window(w.window_id)
            logger.info(
                "Topic closed: killed window %s (user=%d, thread=%d)",
                display,
                user.id,
                thread_id,
            )
        else:
            logger.info(
                "Topic closed: window %s already gone (user=%d, thread=%d)",
                display,
                user.id,
                thread_id,
            )
        session_manager.unbind_thread(user.id, thread_id)
        # Clean up all memory state for this topic
        await clear_topic_state(user.id, thread_id, context.bot, context.user_data)
    else:
        logger.debug(
            "Topic closed: no binding (user=%d, thread=%d)", user.id, thread_id
        )


async def topic_edited_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle topic rename — sync new name to tmux window and internal state."""
    user = update.effective_user
    if not user or not is_user_allowed(user.id):
        return

    msg = update.message
    if not msg or not msg.forum_topic_edited:
        return

    new_name = msg.forum_topic_edited.name
    if new_name is None:
        # Icon-only change, no rename needed
        return

    thread_id = _get_thread_id(update)
    if thread_id is None:
        return

    wid = session_manager.get_window_for_thread(user.id, thread_id)
    if not wid:
        logger.debug(
            "Topic edited: no binding (user=%d, thread=%d)", user.id, thread_id
        )
        return

    old_name = session_manager.get_display_name(wid)
    await tmux_manager.rename_window(wid, new_name)
    session_manager.update_display_name(wid, new_name)
    logger.info(
        "Topic renamed: '%s' -> '%s' (window=%s, user=%d, thread=%d)",
        old_name,
        new_name,
        wid,
        user.id,
        thread_id,
    )


async def _create_and_bind_window(
    query: object,
    context: ContextTypes.DEFAULT_TYPE,
    user: object,
    selected_path: str,
    pending_thread_id: int | None,
    resume_session_id: str | None = None,
) -> None:
    """Create a tmux window, bind it to a topic, and forward pending text.

    Shared by CB_DIR_CONFIRM (no sessions), CB_SESSION_NEW, and CB_SESSION_SELECT.
    """
    assert isinstance(query, CallbackQuery)
    assert isinstance(user, User)

    success, message, created_wname, created_wid = await tmux_manager.create_window(
        selected_path, resume_session_id=resume_session_id
    )
    if success:
        logger.info(
            "Window created: %s (id=%s) at %s (user=%d, thread=%s, resume=%s)",
            created_wname,
            created_wid,
            selected_path,
            user.id,
            pending_thread_id,
            resume_session_id,
        )
        # Wait for Claude Code's SessionStart hook to register in session_map.
        # Resume sessions take longer to start (loading session state), so use
        # a longer timeout to avoid silently dropping messages.
        hook_timeout = 15.0 if resume_session_id else 5.0
        hook_ok = await session_manager.wait_for_session_map_entry(
            created_wid, timeout=hook_timeout
        )

        # --resume creates a new session_id in the hook, but messages continue
        # writing to the resumed session's JSONL file. Override window_state to
        # track the original session_id so the monitor can route messages back.
        if resume_session_id:
            ws = session_manager.get_window_state(created_wid)
            if not hook_ok:
                # Hook timed out — manually populate window_state so the
                # monitor can still route messages back to this topic.
                logger.warning(
                    "Hook timed out for resume window %s, "
                    "manually setting session_id=%s cwd=%s",
                    created_wid,
                    resume_session_id,
                    selected_path,
                )
                ws.session_id = resume_session_id
                ws.cwd = str(selected_path)
                ws.window_name = created_wname
                session_manager._save_state()
            elif ws.session_id != resume_session_id:
                logger.info(
                    "Resume override: window %s session_id %s -> %s",
                    created_wid,
                    ws.session_id,
                    resume_session_id,
                )
                ws.session_id = resume_session_id
                session_manager._save_state()

        if pending_thread_id is not None:
            # Thread bind flow: bind thread to newly created window
            session_manager.bind_thread(
                user.id, pending_thread_id, created_wid, window_name=created_wname
            )

            # Rename the topic to match the window name
            resolved_chat = session_manager.resolve_chat_id(user.id, pending_thread_id)
            try:
                await context.bot.edit_forum_topic(
                    chat_id=resolved_chat,
                    message_thread_id=pending_thread_id,
                    name=created_wname,
                )
            except Exception as e:
                logger.debug(f"Failed to rename topic: {e}")

            status = "Resumed" if resume_session_id else "Created"
            await safe_edit(
                query,
                f"{message}\n\n{status}. Send messages here.",
            )

            # Send pending text if any
            pending_text = (
                context.user_data.get("_pending_thread_text")
                if context.user_data
                else None
            )
            if pending_text:
                logger.debug(
                    "Forwarding pending text to window %s (len=%d)",
                    created_wname,
                    len(pending_text),
                )
                if context.user_data is not None:
                    context.user_data.pop("_pending_thread_text", None)
                    context.user_data.pop("_pending_thread_id", None)
                send_ok, send_msg = await session_manager.send_to_window(
                    created_wid,
                    pending_text,
                )
                if not send_ok:
                    logger.warning("Failed to forward pending text: %s", send_msg)
                    await safe_send(
                        context.bot,
                        resolved_chat,
                        f"Failed to send pending message: {send_msg}",
                        message_thread_id=pending_thread_id,
                    )
            elif context.user_data is not None:
                context.user_data.pop("_pending_thread_id", None)
        else:
            # Should not happen in topic-only mode, but handle gracefully
            await safe_edit(query, f"{message}")
    else:
        await safe_edit(query, f"{message}")
        if pending_thread_id is not None and context.user_data is not None:
            context.user_data.pop("_pending_thread_id", None)
            context.user_data.pop("_pending_thread_text", None)
    await query.answer("Created" if success else "Failed")
