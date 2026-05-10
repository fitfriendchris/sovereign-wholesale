#!/usr/bin/env bash
# Boot the Sovereign stack: Telegram bridge (which fronts Hermes) + scheduler.
# Run in foreground for testing; under launchd for 24/7.

set -euo pipefail
cd "$(dirname "$0")"

# Sanity checks
[ -f .env ] || { echo "✗ .env missing — copy .env.example and fill in keys"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "✗ python3 not found"; exit 1; }

# Ollama health
if ! curl -sS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "⚠ Ollama not responding on :11434 — Hermes will fall back to OpenRouter"
fi

mkdir -p state/logs
echo "[$(date)] starting Sovereign stack"

# Scheduler in background; Telegram bridge in foreground.
python3 -m dispatch.scheduler --loop &
SCHED_PID=$!
trap "echo 'shutting down'; kill $SCHED_PID 2>/dev/null || true" EXIT INT TERM

echo "[$(date)] scheduler PID=$SCHED_PID"
echo "[$(date)] starting telegram bridge"
python3 -m dispatch.telegram_bridge --loop
