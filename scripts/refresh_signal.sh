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

/usr/bin/python3 generate.py

# Commit/push only if generated files changed
if ! /usr/bin/git diff --quiet -- index.html portfolio/index.html portfolio/evolutionfund/index.html stats.json feed.json; then
  /usr/bin/git add index.html portfolio/index.html portfolio/evolutionfund/index.html feed.json
  [ -f stats.json ] && /usr/bin/git add -f stats.json
  /usr/bin/git commit -m "chore: scheduled Signal refresh $(date -u '+%Y-%m-%d %H:%M UTC')" || true
  /usr/bin/git push origin main || true
fi
