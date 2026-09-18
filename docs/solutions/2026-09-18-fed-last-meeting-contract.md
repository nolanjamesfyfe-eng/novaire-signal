---
tags: [novaire-signal, fed, generated-dashboard, reliability, visual-lock]
---

# Fed last-meeting display and refresh contract

## Approved visual baseline (locked September 18, 2026)

- Render `Last meeting` between `Rate` and `Next FOMC`; keep four columns on desktop and a two-by-two grid below 520px.
- Keep the current typography and value hierarchy unchanged.
- Keep desktop columns `.9fr 1.2fr 1.2fr 1fr` and `.fed-fomc` left padding at `28px`.
- Preserve the existing FedWatch presentation and data path. This reliability change does not authorize a redesign or FedWatch changes.
- `scripts/validate_fed_signal.py` is the independent fail-closed layout/data guard. Change its visual fingerprints only after explicit design approval.

## Reliability contract

- `fed_signal.py` retrieves meeting dates from the Federal Reserve's official FOMC calendar and decision/rate facts from the latest released official FOMC statement.
- Validate provenance, canonical/display date agreement, action vocabulary, target-range shape and chronology before accepting data.
- Write `fed_signal_cache.json` atomically only after the complete official result validates.
- If official retrieval or parsing fails, retain and render the validated last-good cache without modifying it. Never infer, guess or synthesize replacement Fed facts.
- If both retrieval and cache validation fail, abort generation. The scheduled refresh must validate generated Fed facts against the cache before commit/push.
- Keep source changes in the generator path and regenerate `index.html`; never patch generated HTML alone.
- The cache may preserve stale-but-verified values during an outage. This is deliberate and safer than an invented update; freshness resumes when official retrieval validates again.
