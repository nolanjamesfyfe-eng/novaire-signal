---
tags: [fed-signal, generated-dashboard, factual-provenance, responsive-layout]
---

# Fed last-meeting display contract

- Keep Fed decision facts in `fetch_fed_signal()` and regenerate `index.html`; never patch generated HTML alone.
- Source the action from the Federal Reserve's official FOMC statement. Store the source URL beside the hardcoded fact so the next update has explicit provenance.
- Render `Last meeting` between `Rate` and `Next FOMC`, with the date using the existing serif value style and the action using the existing small secondary style.
- Preserve existing type sizes. Fit four desktop columns by changing only column proportions and a small left-padding shift on `Next FOMC`; use a two-by-two mobile grid below 520 px.