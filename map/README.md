# Travel map data

`visited.json` is the canonical public record used by `/map`. The page reloads it with `cache: no-store` on initial load and every 60 seconds. There is no browser write endpoint.

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
