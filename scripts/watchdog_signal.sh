#!/usr/bin/env bash
set -euo pipefail
cd /root/clawd/novaire-signal
PYTHON_BIN="${NOVAIRE_SIGNAL_PYTHON:-/usr/local/lib/hermes-agent/venv/bin/python3}"
printf '[%s] WATCHDOG checking canonical freshness\n' "$(date -Is)"
if "$PYTHON_BIN" scripts/verify_live_freshness.py --attempts 1 --delay 0; then
  printf '[%s] WATCHDOG healthy\n' "$(date -Is)"
  exit 0
fi
printf '[%s] WATCHDOG stale; launching self-repair refresh\n' "$(date -Is)"
scripts/refresh_signal.sh
"$PYTHON_BIN" scripts/verify_live_freshness.py --attempts 3 --delay 20
printf '[%s] WATCHDOG repaired canonical page\n' "$(date -Is)"
