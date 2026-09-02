#!/usr/bin/env bash
set -euo pipefail

cd /root/clawd/novaire-signal

LOG_DIR=/root/clawd/logs
STATE_FILE="$LOG_DIR/novaire-signal-refresh-state.json"
LOCK_FILE=/run/lock/novaire-signal-refresh.lock
mkdir -p "$LOG_DIR"

exec 9>"$LOCK_FILE"
if ! /usr/bin/flock -n 9; then
  printf '[%s] SKIP: another Novaire Signal refresh is running\n' "$(date -Is)"
  exit 0
fi

set -a
[ -f /root/clawd/.secrets ] && source /root/clawd/.secrets
[ -f /root/clawd/config/tokens.env ] && source /root/clawd/config/tokens.env
set +a

PYTHON_BIN="${NOVAIRE_SIGNAL_PYTHON:-/usr/local/lib/hermes-agent/venv/bin/python3}"
ARTIFACTS=(index.html portfolio/index.html portfolio/daily/index.html portfolio/evolutionfund/index.html feed.json portfolio_history.json stats.json weather_cache.json)
STAGE="startup"

log() { printf '[%s] %s\n' "$(date -Is)" "$*"; }
write_state() {
  local status="$1" detail="${2:-}"
  STATUS="$status" DETAIL="$detail" STAGE_VALUE="$STAGE" "$PYTHON_BIN" - <<'PY'
import json, os
from datetime import datetime, timezone
from pathlib import Path
path = Path('/root/clawd/logs/novaire-signal-refresh-state.json')
previous = {}
try:
    previous = json.loads(path.read_text())
except Exception:
    pass
now = datetime.now(timezone.utc).isoformat()
state = {
    'status': os.environ['STATUS'],
    'stage': os.environ['STAGE_VALUE'],
    'detail': os.environ.get('DETAIL', ''),
    'updated_at': now,
    'last_success_at': now if os.environ['STATUS'] == 'success' else previous.get('last_success_at'),
}
path.write_text(json.dumps(state, indent=2) + '\n')
PY
}
fail() {
  local code=$? line=${BASH_LINENO[0]:-unknown}
  write_state failed "stage=$STAGE line=$line exit=$code"
  log "FAILED stage=$STAGE line=$line exit=$code"
  exit "$code"
}
trap fail ERR

retry() {
  local attempts="$1" delay="$2" label="$3"; shift 3
  local n=1
  until "$@"; do
    if (( n >= attempts )); then
      log "FAILED after $attempts attempts: $label"
      return 1
    fi
    log "Retry $n/$attempts for $label in ${delay}s"
    sleep "$delay"
    n=$((n + 1))
  done
}

restore_artifacts() {
  /usr/bin/git restore -- "${ARTIFACTS[@]}" 2>/dev/null || true
}

generate_and_validate() {
  if ! "$PYTHON_BIN" generate.py; then
    restore_artifacts
    return 1
  fi
  if ! "$PYTHON_BIN" scripts/validate_generated_quotes.py; then
    restore_artifacts
    return 1
  fi
}

sync_and_push() {
  if /usr/bin/git push origin main; then
    return 0
  fi
  log 'Push rejected; synchronizing once before retry'
  /usr/bin/git pull --rebase --autostash origin main
  /usr/bin/git push origin main
}

write_state running 'refresh started'
log 'START Novaire Signal refresh'

STAGE="runtime-check"
if [ ! -x "$PYTHON_BIN" ] || ! "$PYTHON_BIN" -c 'import requests, bs4, yfinance' >/dev/null 2>&1; then
  log "Missing required Python runtime/dependencies: $PYTHON_BIN"
  exit 1
fi

STAGE="git-sync"
retry 3 20 'git pull' /usr/bin/git pull --rebase --autostash origin main

STAGE="generate-validate"
retry 3 90 'generation and quote validation' generate_and_validate

STAGE="commit"
if ! /usr/bin/git diff --quiet -- "${ARTIFACTS[@]}"; then
  /usr/bin/git add index.html portfolio/index.html portfolio/daily/index.html portfolio/evolutionfund/index.html feed.json portfolio_history.json
  [ -f stats.json ] && /usr/bin/git add -f stats.json
  [ -f weather_cache.json ] && /usr/bin/git add weather_cache.json
  /usr/bin/git commit -m "chore: scheduled Signal refresh $(date -u '+%Y-%m-%d %H:%M UTC')"
else
  log 'No generated artifact changes to commit'
fi

STAGE="git-push"
retry 3 30 'git push' sync_and_push
LOCAL_HEAD=$(/usr/bin/git rev-parse HEAD)
REMOTE_HEAD=$(/usr/bin/git ls-remote origin refs/heads/main | /usr/bin/cut -f1)
if [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  log "Remote verification mismatch local=$LOCAL_HEAD remote=$REMOTE_HEAD"
  exit 1
fi

STAGE="live-verification"
retry 2 30 'live deployment verification' "$PYTHON_BIN" scripts/verify_live_freshness.py --attempts 12 --delay 20

STAGE="complete"
write_state success "commit=$LOCAL_HEAD"
log "SUCCESS commit=$LOCAL_HEAD live date verified"
