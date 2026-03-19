#!/usr/bin/env bash
set -euo pipefail

TMUX_SESSION="ccbot"
TMUX_WINDOW="__main__"
TARGET="${TMUX_SESSION}:${TMUX_WINDOW}"
MAX_WAIT=10

if ! tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo "No tmux session '$TMUX_SESSION' found"
    exit 0
fi

if ! tmux list-windows -t "$TMUX_SESSION" -F '#{window_name}' 2>/dev/null | grep -qx "$TMUX_WINDOW"; then
    echo "No __main__ window found"
    exit 0
fi

PANE_PID=$(tmux list-panes -t "$TARGET" -F '#{pane_pid}')

echo "Sending Ctrl-C to ccbot..."
tmux send-keys -t "$TARGET" C-c

waited=0
while ps -o command= -g "$PANE_PID" 2>/dev/null | grep -q 'ccbot' && [ "$waited" -lt "$MAX_WAIT" ]; do
    sleep 1
    waited=$((waited + 1))
    echo "  Waiting... (${waited}s/${MAX_WAIT}s)"
done

if ps -o command= -g "$PANE_PID" 2>/dev/null | grep -q 'ccbot'; then
    echo "Force killing..."
    CCBOT_PID=$(ps -o pid=,command= -g "$PANE_PID" 2>/dev/null | grep 'ccbot' | awk '{print $1}' | head -1)
    if [ -n "$CCBOT_PID" ]; then
        kill -9 "$CCBOT_PID" 2>/dev/null || true
    fi
fi

echo "CCBot stopped."
