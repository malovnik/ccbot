#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMUX_SESSION="ccbot"

echo "CCBot startup script"
echo "Project: ${PROJECT_DIR}"

# Check dependencies
if ! command -v tmux &>/dev/null; then
    echo "Error: tmux is not installed"
    exit 1
fi

if ! command -v uv &>/dev/null; then
    echo "Error: uv is not installed"
    exit 1
fi

# Check .env exists
if [ ! -f "${HOME}/.ccbot/.env" ] && [ ! -f "${PROJECT_DIR}/.env" ]; then
    echo "Error: No .env found"
    echo "Copy .env.example to ~/.ccbot/.env and configure it:"
    echo "  mkdir -p ~/.ccbot"
    echo "  cp ${PROJECT_DIR}/.env.example ~/.ccbot/.env"
    exit 1
fi

# Install hook if not installed
echo "Checking Claude Code hook..."
cd "$PROJECT_DIR" && uv run ccbot hook --install 2>/dev/null || true

# Create or attach to tmux session
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo "tmux session '$TMUX_SESSION' already exists"

    # Check if __main__ window exists and ccbot is running
    if tmux list-windows -t "$TMUX_SESSION" -F '#{window_name}' | grep -qx "__main__"; then
        PANE_PID=$(tmux list-panes -t "${TMUX_SESSION}:__main__" -F '#{pane_pid}')
        if ps -o command= -g "$PANE_PID" 2>/dev/null | grep -q 'ccbot'; then
            echo "ccbot is already running. Use scripts/restart.sh to restart."
            exit 0
        fi
    fi
else
    echo "Creating tmux session '$TMUX_SESSION'..."
    tmux new-session -d -s "$TMUX_SESSION" -n "__main__"
fi

# Start ccbot in the __main__ window
echo "Starting ccbot..."
tmux send-keys -t "${TMUX_SESSION}:__main__" "cd ${PROJECT_DIR} && uv run ccbot" Enter

echo ""
echo "CCBot started in tmux session '$TMUX_SESSION'"
echo "  Attach:  tmux attach -t $TMUX_SESSION"
echo "  Restart: ./scripts/restart.sh"
echo "  Logs:    tail -f ~/.ccbot/ccbot.log"
