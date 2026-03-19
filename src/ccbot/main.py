"""Application entry point — CLI dispatcher and bot bootstrap.

Handles three execution modes:
  1. `ccbot hook` — delegates to hook.hook_main() for Claude Code hook processing.
  2. `ccbot web` — runs WS bridge server only (no Telegram bot).
  3. Default — configures logging, initializes tmux session, and starts the
     Telegram bot polling loop via bot.create_bot().
     With `--with-web` flag, also starts WS bridge alongside the bot.
"""

import asyncio
import logging
import sys


def _setup_logging() -> logging.Logger:
    """Configure logging (console + file rotation). Returns ccbot logger."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.WARNING,
    )

    import os as _os
    from logging.handlers import RotatingFileHandler

    from .config import config

    log_file = config.config_dir / "ccbot.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    if log_file.exists():
        _os.chmod(log_file, 0o600)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    file_handler.setLevel(logging.DEBUG)
    logging.getLogger("ccbot").addHandler(file_handler)
    logging.getLogger("ccbot").setLevel(logging.DEBUG)
    logging.getLogger("telegram.ext.AIORateLimiter").setLevel(logging.INFO)

    return logging.getLogger(__name__)


def _run_web_only() -> None:
    """Run WS bridge server without Telegram bot."""
    try:
        from .config import config
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    logger = _setup_logging()

    from .session_monitor import SessionMonitor
    from .tmux_manager import tmux_manager
    from .ws_bridge import WsBridge

    session = tmux_manager.get_or_create_session()
    logger.info("Tmux session '%s' ready", session.session_name)

    async def run() -> None:
        bridge = WsBridge(host=config.ws_host, port=config.ws_port)
        await bridge.start()

        monitor = SessionMonitor()
        monitor.set_message_callback(bridge.on_new_message)
        monitor.start()
        logger.info("Session monitor started (WS-only mode)")

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            monitor.stop()
            await bridge.stop()

    logger.info("Starting WS bridge on %s:%d...", config.ws_host, config.ws_port)
    asyncio.run(run())


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "hook":
        from .hook import hook_main

        hook_main()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "web":
        _run_web_only()
        return

    with_web = "--with-web" in sys.argv
    if with_web:
        sys.argv.remove("--with-web")

    try:
        from .config import config
    except ValueError as e:
        from .utils import ccbot_dir

        config_dir = ccbot_dir()
        env_path = config_dir / ".env"
        print(f"Error: {e}\n")
        print(f"Create {env_path} with the following content:\n")
        print("  TELEGRAM_BOT_TOKEN=your_bot_token_here")
        print("  ALLOWED_USERS=your_telegram_user_id")
        print()
        print("Get your bot token from @BotFather on Telegram.")
        print("Get your user ID from @userinfobot on Telegram.")
        sys.exit(1)

    logger = _setup_logging()

    from importlib.metadata import version as pkg_version

    try:
        ver = pkg_version("ccbot")
    except Exception:
        ver = "dev"
    logger.info("CCBot v%s starting", ver)

    from .tmux_manager import tmux_manager

    logger.info("Allowed users: %s", config.allowed_users)
    logger.info("Claude projects path: %s", config.claude_projects_path)

    session = tmux_manager.get_or_create_session()
    logger.info("Tmux session '%s' ready", session.session_name)

    if with_web or config.ws_enabled:
        import ccbot.ws_bridge as _ws_mod

        from .ws_bridge import WsBridge

        _ws_mod.ws_bridge = WsBridge(host=config.ws_host, port=config.ws_port)
        logger.info(
            "WS bridge will start on %s:%d alongside Telegram bot",
            config.ws_host,
            config.ws_port,
        )

    logger.info("Starting Telegram bot...")
    from .bot import create_bot

    application = create_bot()
    application.run_polling(
        allowed_updates=[
            "message",
            "edited_message",
            "callback_query",
            "message_reaction",
        ]
    )


if __name__ == "__main__":
    main()
