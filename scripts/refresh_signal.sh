#!/usr/bin/env bash
set -euo pipefail

cd /root/clawd/novaire-signal

# Cron starts with a bare environment; load API credentials for Alpaca/Kraken/Vercel/etc.
set -a
[ -f /root/clawd/.secrets ] && source /root/clawd/.secrets
[ -f /root/clawd/config/tokens.env ] && source /root/clawd/config/tokens.env
set +a

# Keep branch current without destructive reset (preserves intentional local edits)
/usr/bin/git pull --rebase --autostash origin main || true

# Use the Hermes runtime that owns the dashboard dependencies. Fail closed before
# generation rather than publishing a stripped page from bare /usr/bin/python3.
PYTHON_BIN="${NOVAIRE_SIGNAL_PYTHON:-/usr/local/lib/hermes-agent/venv/bin/python3}"
if [ ! -x "$PYTHON_BIN" ] || ! "$PYTHON_BIN" -c 'import requests, bs4, yfinance' >/dev/null 2>&1; then
  echo "ERROR: Novaire Signal Python runtime is missing required dependencies: $PYTHON_BIN" >&2
  exit 1
fi

"$PYTHON_BIN" generate.py

# Commit/push only if generated files changed
if ! /usr/bin/git diff --quiet -- index.html portfolio/index.html portfolio/evolutionfund/index.html stats.json feed.json weather_cache.json; then
  /usr/bin/git add index.html portfolio/index.html portfolio/evolutionfund/index.html feed.json
  [ -f stats.json ] && /usr/bin/git add -f stats.json
  [ -f weather_cache.json ] && /usr/bin/git add weather_cache.json
  /usr/bin/git commit -m "chore: scheduled Signal refresh $(date -u '+%Y-%m-%d %H:%M UTC')" || true
  /usr/bin/git push origin main || true
fi
