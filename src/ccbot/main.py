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


def _show_status() -> None:
    """Show current ccbot status: config, tmux sessions, state files."""
    import json

    from .utils import ccbot_dir

    config_dir = ccbot_dir()
    print(f"Config dir: {config_dir}")
    print(f"  .env exists: {(config_dir / '.env').exists()}")

    state_file = config_dir / "state.json"
    session_map = config_dir / "session_map.json"

    if session_map.exists():
        try:
            data = json.loads(session_map.read_text())
            print(f"\nSession map: {len(data)} entries")
            for key, info in data.items():
                sid = info.get("session_id", "?")[:8]
                wname = info.get("window_name", "?")
                cwd = info.get("cwd", "?")
                print(f"  {key}: {wname} (session {sid}...) @ {cwd}")
        except (json.JSONDecodeError, OSError):
            print("\nSession map: error reading")
    else:
        print("\nSession map: not found (no hook fired yet)")

    if state_file.exists():
        try:
            data = json.loads(state_file.read_text())
            bindings = data.get("thread_bindings", {})
            total_bindings = sum(len(v) for v in bindings.values())
            print(f"\nThread bindings: {total_bindings}")
        except (json.JSONDecodeError, OSError):
            print("\nState: error reading")
    else:
        print("\nState: not found (bot never started)")

    import subprocess

    try:
        result = subprocess.run(
            [
                "tmux",
                "list-windows",
                "-t",
                "ccbot",
                "-F",
                "#{window_id} #{window_name} #{pane_current_path}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            windows = result.stdout.strip().split("\n")
            print(f"\nTmux session 'ccbot': {len(windows)} windows")
            for w in windows:
                print(f"  {w}")
        else:
            print("\nTmux session 'ccbot': not found")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("\nTmux: not available")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        from importlib.metadata import version as pkg_version

        try:
            ver = pkg_version("ccbot")
        except Exception:
            ver = "dev"
        print(f"ccbot {ver} — Telegram bridge for Claude Code sessions")
        print()
        print("Usage:")
        print("  ccbot                 Start Telegram bot")
        print("  ccbot --with-web      Start bot + WebSocket bridge")
        print("  ccbot web             Start WebSocket bridge only")
        print("  ccbot hook            Process Claude Code SessionStart hook")
        print("  ccbot hook --install  Install hook into Claude settings")
        print("  ccbot version         Show version")
        print("  ccbot status          Show tmux sessions and config")
        return

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        _show_status()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "version":
        from importlib.metadata import version as pkg_version

        try:
            ver = pkg_version("ccbot")
        except Exception:
            ver = "dev"
        print(f"ccbot {ver}")
        return

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
