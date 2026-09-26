#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_session=echotrace-api
web_session=echotrace-web
api_url=http://127.0.0.1:8000/api/health
web_url=http://127.0.0.1:5173/

command -v tmux >/dev/null || { echo "Install tmux or use the two-terminal setup in README.md." >&2; exit 1; }

healthy() {
  curl --silent --fail --max-time 2 "$api_url" >/dev/null &&
    curl --silent --fail --max-time 2 "$web_url" >/dev/null
}

case "${1:-start}" in
  start)
    if ! tmux has-session -t "$api_session" 2>/dev/null; then
      tmux new-session -d -s "$api_session" -c "$project_dir/backend" \
        'uv run uvicorn echotrace.api:app --host 127.0.0.1 --port 8000'
    fi
    if ! tmux has-session -t "$web_session" 2>/dev/null; then
      tmux new-session -d -s "$web_session" -c "$project_dir/frontend" \
        'npm run dev -- --port 5173'
    fi
    for ((attempt=0; attempt<30; attempt++)); do
      if healthy; then
        echo "ECHOTRACE is ready at $web_url"
        exit 0
      fi
      sleep 0.5
    done
    echo "ECHOTRACE did not become ready. Inspect the detached sessions:" >&2
    echo "  tmux capture-pane -pt $api_session -S -60" >&2
    echo "  tmux capture-pane -pt $web_session -S -60" >&2
    exit 1
    ;;
  status)
    if healthy; then
      echo "ECHOTRACE is ready at $web_url"
    else
      echo "ECHOTRACE is not fully running. Start it with: ./scripts/dev.sh start"
      exit 1
    fi
    ;;
  stop)
    for session in "$web_session" "$api_session"; do
      if tmux has-session -t "$session" 2>/dev/null; then
        tmux kill-session -t "$session"
      fi
    done
    echo "ECHOTRACE local servers stopped."
    ;;
  *)
    echo "Usage: ./scripts/dev.sh [start|status|stop]" >&2
    exit 2
    ;;
esac
