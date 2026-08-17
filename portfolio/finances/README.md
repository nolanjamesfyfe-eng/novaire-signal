# On The Rise Finances

Standalone, dependency-free debt dashboard served at `/portfolio/finances/`.

## Regenerate

```bash
python3 scripts/generate_finances.py
python3 -m unittest tests.test_generate_finances -v
```

To move the actual/projection boundary after a sync:

```bash
python3 scripts/generate_finances.py --current-period 2026-09-01
```

At runtime, a synced feed can update the displayed period without rebuilding:

```js
window.OnTheRiseFinances.setCurrentPeriod('2026-09-01')
```

The active value is also available as `document.documentElement.dataset.currentPeriod`.

## Connect the Google Sheet

Source Sheet ID: `1rqRNI6z3rqXGCMlPbsbVEJUw82DCskU9qf9sKEXMnak`

Once the Google Sheets read scope is granted:

1. Grant the runtime/service account access to the sheet.
2. Read the sheet with `spreadsheets.values.get` using scope `https://www.googleapis.com/auth/spreadsheets.readonly`.
3. Map columns to the stable `data.json` keys: `date`, `visa`, `line`, `total_debt`, `visa_interest`, `line_interest`, `total_interest`, `annual_interest`.
4. Set `current_period` to the latest verified actual row and mark later rows `projection`.
5. Write the normalized payload atomically to `portfolio/finances/data.json`, then run this generator (or inject that payload into the template).
6. Validate totals before publishing: `visa + line == total_debt` for the source convention, and `visa_interest + line_interest == total_interest` (allowing documented source rounding).

Do not expose Sheets credentials in generated HTML or JSON. The current generated data is a screenshot-derived seed, recorded in `data.json` under `source.type`.
