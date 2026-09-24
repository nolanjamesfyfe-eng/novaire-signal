# Travel map data

`visited.json` is the canonical public record used by `/flaneur`. Legacy `/map`, `/map/`, and `/map/index.html` redirect permanently to `/flaneur`; source and data assets remain in `map/`. The page reloads visited data with `cache: no-store` on initial load and every 60 seconds. There is no browser write endpoint.

## Personal wishlist

The single-column ranking is separate from orange upcoming trips. `wishlist.js` stores validated ISO codes and lock state in `localStorage` under `novaire.flaneur.wishlist.v1`. Edit ranking unlocks rank/country cells, up/down and remove controls, plus the bottom add-country row. Each valid edit saves immediately; Save & Lock hides editing controls and persists the lock. Additional countries extend the list and its heading count. Data persists only on the same browser/origin, not across devices, and never changes the public visited/planned record. Storage failures do not claim a successful save or lock.

The approved heading is `Flâneur Happenings`, with circumflex, one line, 15% smaller desktop type than the initial version, no supporting paragraph. Browser testing must cover 320px/390px mobile widths, rank changes, country additions/replacements, duplicates, save/lock/reload, and blocked storage. Run `node --test tests/wishlist.test.cjs` plus `python -m pytest tests/test_map_route.py tests/test_map_flaneur.py`.

## Globe detail and navigation

The canvas uses four topology-clean Natural Earth 1:10m LODs. The 20% high tier
(`world-globe-high.geojson`) is fetched only at 3× zoom, cached after success,
and cancelled if an unfinished request is no longer needed. The previous tier
stays painted during loading or failure. The finite 72× ceiling makes compact
jurisdictions such as Monaco distinguishable, but this remains regional/coastline
detail—not street, parcel, or surveyed boundary data. World-scale small-place
circles are location markers and disappear before boundary-level zoom.

Yaw is deliberately unbounded for repeated full turns; pitch stops at ±89.5°.
Overview touch keeps vertical page scrolling, while zoomed touch captures both
axes for globe rotation. Wheel and pinch zoom remain anchored under the pointer
or pinch midpoint. Search `Hawaii` for the explicitly labelled US place focus;
Hong Kong and Monaco remain jurisdiction features in the 199-entry atlas.

## Record answers safely

From the repository root:

```bash
python map/update_visited.py CA=true FR=false JP=true
```

- Use ISO 3166-1 alpha-2 codes from `map/countries.json`.
- `true` means visited, `false` means explicitly not visited.
- Missing codes remain **unanswered**. Never convert missing answers to `false`.
- The updater validates every code/value, preserves existing answers, sorts keys, and writes `updatedAt`.

Review and publish only these data changes:

```bash
git diff -- map/visited.json
git add map/visited.json
git commit -m "data: update public travel answers"
git push origin main
```

## Data contract

```json
{
  "answers": {
    "CA": true,
    "FR": false
  },
  "updatedAt": "2026-09-16T00:00:00Z"
}
```

The catalog contains 199 tracked destinations: the 195-country baseline (193 UN members plus Palestine and Vatican City), plus Taiwan, Kosovo, Hong Kong, and Macau, explicitly confirmed visited. This is not an exhaustive territories list. The percentage uses this 199-entry atlas. Kosovo uses the user-assigned code XK. Additional geometry is sourced from Natural Earth ne_10m_admin_0_countries.geojson; Hong Kong and Macau also have visible markers. `world.geojson` contains Natural Earth country geometry. Small island nations and microstates also receive visible point markers at world scale.

## Capital, population, and GDP facts

`country_facts.json` covers the same 199 codes as the catalog and geometry. Each
entry stores its capital source URL and the population source URL, unrounded
value, actual reference year, and rank across 219 non-aggregate World Bank/UN
economies. Taiwan and Vatican City use UN WPP 2024 because World Bank has no
series; other population observations currently use 2025. `refreshedAt` is
retrieval metadata, never an observation year.

Nominal GDP is IMF WEO `NGDPD`, current U.S. dollars (source units: USD
billions), reference year 2025. Values are estimates in the April 2026 WEO
vintage. GDP ranks cover the 193 IMF country/economy codes with a 2025 value;
regional and analytical aggregates are excluded using the IMF countries
endpoint. Missing IMF coverage renders `N/A` with no invented rank. Refreshes
retain a prior complete ranked snapshot on upstream failure rather than mixing
fresh values with stale ranks.

Refresh and validate without writing:

```bash
python3 map/refresh_country_facts.py --dry-run
```

Refresh locally, validate the data contract, and run the map integration tests:

```bash
python3 map/refresh_country_facts.py
python3 map/refresh_country_facts.py --check
python3 -m pytest tests/test_map_route.py
```

Quarterly publication is handled by `scripts/refresh_map_facts.sh` in an
isolated temporary Git worktree. It stages only `map/country_facts.json`, so
unrelated work in the primary checkout cannot leak into its commit.
