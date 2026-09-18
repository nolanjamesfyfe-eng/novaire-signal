#!/usr/bin/env bash
set -euo pipefail

REPO=/root/clawd/novaire-signal
LOCK=/run/lock/novaire-signal-map-facts.lock
MODE=${1:-publish}
exec 9>"$LOCK"
/usr/bin/flock -n 9 || { printf 'Another map facts refresh is running\n'; exit 0; }

if [[ "$MODE" == "--dry-run" ]]; then
  cd "$REPO"
  exec /usr/bin/python3 map/refresh_country_facts.py --dry-run
fi
if [[ "$MODE" != "publish" ]]; then
  printf 'Usage: %s [--dry-run]\n' "$0" >&2
  exit 2
fi

WORKTREE=$(/usr/bin/mktemp -d /tmp/novaire-map-facts.XXXXXX)
cleanup() {
  /usr/bin/git -C "$REPO" worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  /usr/bin/rmdir "$WORKTREE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

/usr/bin/git -C "$REPO" fetch origin main
/usr/bin/git -C "$REPO" worktree add --detach "$WORKTREE" origin/main
cd "$WORKTREE"
/usr/bin/python3 map/refresh_country_facts.py
/usr/bin/python3 map/refresh_country_facts.py --check
/usr/bin/python3 -m pytest -q tests/test_map_route.py

if /usr/bin/git diff --quiet -- map/country_facts.json; then
  printf 'Map facts unchanged; nothing to publish\n'
  exit 0
fi

/usr/bin/git add map/country_facts.json
/usr/bin/git diff --cached --quiet && exit 0
/usr/bin/git commit -m "data: quarterly map facts refresh $(TZ=Asia/Bangkok date '+%Y-%m-%d BKK')"
/usr/bin/git push origin HEAD:main
COMMIT=$(/usr/bin/git rev-parse HEAD)
REMOTE=$(/usr/bin/git ls-remote origin refs/heads/main | /usr/bin/cut -f1)
[[ "$COMMIT" == "$REMOTE" ]] || { printf 'Remote commit mismatch\n' >&2; exit 1; }

# Vercel Git deployment can lag the push. Verify both assets from the canonical domain.
for attempt in $(/usr/bin/seq 1 20); do
  stamp=$(/usr/bin/date +%s)
  facts=$(/usr/bin/curl -fsS "https://novairesignal.com/map/country_facts.json?t=$stamp" || true)
  html=$(/usr/bin/curl -fsS "https://novairesignal.com/map/?t=$stamp" || true)
  if FACTS="$facts" HTML="$html" /usr/bin/python3 - <<'PY'
import json, os
try:
    data = json.loads(os.environ['FACTS'])
except Exception:
    raise SystemExit(1)
assert data['coverage']['mapped'] == 199
assert data['coverage']['capitalFilled'] == 199
assert data['coverage']['populationFilled'] == 199
assert set(data['countries']) == {row['iso2'] for row in json.load(open('map/countries.json'))}
assert "fetch('/map/country_facts.json')" in os.environ['HTML']
assert '<b>Capital:</b>' in os.environ['HTML'] and '<b>Population:</b>' in os.environ['HTML']
PY
  then
    printf 'Published and verified map facts commit=%s\n' "$COMMIT"
    exit 0
  fi
  /usr/bin/sleep 15
done
printf 'Push succeeded but canonical live verification timed out for commit=%s\n' "$COMMIT" >&2
exit 1
