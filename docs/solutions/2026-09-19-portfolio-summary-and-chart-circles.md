---
title: Keep portfolio summary singular and chart indicators circular
category: generated-dashboard
component: portfolio-tracker
tags: [portfolio, generated-html, responsive, svg]
---

# Portfolio summary and chart indicator correction

- Treat the interactive `.tracker-hero-value` as the canonical combined net-worth summary. Do not render a second outer rounded total or a redundant `Combined Net Worth` label.
- Keep provenance/history copy inside the chart unless removal is explicitly requested; remove only the named header subtitle.
- Preserve full button hit targets while drawing timeframe state with a centered, equal-width/equal-height `::before` circle. Put the focus-visible ring on that circle so keyboard focus does not recreate a wide capsule.
- An SVG `<circle>` stretches when its parent uses `preserveAspectRatio="none"`. Render the hover marker as an ellipse and calculate `rx`/`ry` from the live SVG DOM dimensions; use `vector-effect="non-scaling-stroke"` so its visible outline stays round.
- Verify desktop and mobile computed indicator geometry, SVG hover-marker bounds, every range transition, hover CAD/ATH values, and mouseleave restoration in a real browser.
- When rebuilding a live-data dashboard for a UI-only correction, do not ship unrelated refreshed values. Restore incidental generated/cache changes and preserve the reviewed canonical value in the generated artifact.
