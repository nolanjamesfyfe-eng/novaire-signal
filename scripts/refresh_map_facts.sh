#!/usr/bin/env bash
set -euo pipefail

REPO=/root/clawd/novaire-signal
PYTHON_BIN=${NOVAIRE_SIGNAL_PYTHON:-/usr/local/lib/hermes-agent/venv/bin/python3}
LOCK=/run/lock/novaire-signal-map-facts.lock
MODE=${1:-publish}
exec 9>"$LOCK"
/usr/bin/flock -n 9 || { printf 'Another map facts refresh is running\n'; exit 0; }

if [[ "$MODE" == "--dry-run" ]]; then
  cd "$REPO"
  exec "$PYTHON_BIN" map/refresh_country_facts.py --dry-run
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
"$PYTHON_BIN" map/refresh_country_facts.py
"$PYTHON_BIN" map/refresh_country_facts.py --check
"$PYTHON_BIN" -m pytest -q tests/test_map_route.py
/usr/bin/node --test tests/map-fact-format.test.cjs

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
FACTS_FILE=$(/usr/bin/mktemp)
HTML_FILE=$(/usr/bin/mktemp)
trap 'rm -f "$FACTS_FILE" "$HTML_FILE"; cleanup' EXIT
for attempt in $(/usr/bin/seq 1 20); do
  stamp=$(/usr/bin/date +%s)
  /usr/bin/curl -fsS "https://novairesignal.com/map/country_facts.json?t=$stamp" -o "$FACTS_FILE" || : >"$FACTS_FILE"
  /usr/bin/curl -fsS "https://novairesignal.com/flaneur?t=$stamp" -o "$HTML_FILE" || : >"$HTML_FILE"
  if /usr/bin/python3 - "$FACTS_FILE" "$HTML_FILE" <<'PY'
import json, re, sys
try:
    data = json.load(open(sys.argv[1]))
    html = open(sys.argv[2]).read()
except Exception:
    raise SystemExit(1)
assert data['coverage']['mapped'] == 199
assert data['coverage']['capitalFilled'] == 199
assert data['coverage']['populationFilled'] == 199
assert data['coverage']['populationRankUniverse'] >= 200
assert data['coverage']['gdpFilled'] >= 185
assert data['sources']['gdpNominal']['referenceYear'] == 2025
assert data['sources']['gdpNominal']['unit'] == 'Billions of U.S. dollars'
for code, fact in data['countries'].items():
    display = fact['capital']['display']
    assert display and display != 'Unavailable', code
    assert not re.search(r'(?<![A-Za-z0-9])Q\d+(?![A-Za-z0-9])', display), code
    assert not display.startswith(('http://', 'https://')), code
    assert isinstance(fact['population']['value'], int) and fact['population']['value'] > 0, code
    assert isinstance(fact['population']['year'], int) and 1950 <= fact['population']['year'] <= 2100, code
    assert isinstance(fact['population']['rank'], int) and fact['population']['rank'] > 0, code
    if fact['gdp']['value'] is not None:
        assert fact['gdp']['year'] == 2025 and fact['gdp']['rank'] > 0, code
assert set(data['countries']) == {row['iso2'] for row in json.load(open('map/countries.json'))}
assert "fetch('/map/country_facts.json')" in html
assert '<b>Capital:</b>' in html and '<b>Population:</b>' in html
assert '<b>GDP:</b>' in html and 'nominal current USD' in html
PY
  then
    printf 'Published and verified map facts commit=%s\n' "$COMMIT"
    exit 0
  fi
  /usr/bin/sleep 15
done
printf 'Push succeeded but canonical live verification timed out for commit=%s\n' "$COMMIT" >&2
exit 1
