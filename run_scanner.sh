#!/usr/bin/env bash
# Boot the 24/7 Opportunity Scanner. Standalone — separate from Hermes.

set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "✗ .env missing"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "✗ python3 not found"; exit 1; }

mkdir -p state/logs
echo "[$(date)] starting scanner loop"
exec python3 -m dispatch.scanner --loop
