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

The catalog contains exactly 195 entries: 193 UN members plus the two UN observer states, Palestine and Vatican City. `world.geojson` contains Natural Earth country geometry. Small island nations and microstates also receive visible point markers at world scale.
