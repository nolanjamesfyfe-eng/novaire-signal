---
title: Fixed full-history ATH comparisons in generated portfolio charts
tags: [novaire-signal, portfolio, generated-dashboard, chart, ath]
---

# Portfolio chart ATH contract

## Acceptance criteria

- The chart summary shows the current value's signed CAD difference and percentage difference from the maximum CAD value in the full available series, labeled `ATH`.
- Hovering any point updates the displayed C$ value and both ATH differences for that point.
- Hovering the peak shows `C$0 (0.00%) · ATH`.
- Pointer leave restores the latest value and its ATH differences.
- Changing chart ranges never changes the ATH baseline; YTD remains the default tab and all existing tabs remain available.
- Chart layout, range-specific line rendering, account cards, and surrounding portfolio metrics remain unchanged.

## Lesson

Compute the ATH once from the unfiltered series before range rendering. Range-filtered points may control geometry and line color, but must never supply the comparison baseline. Route initial render, hover, range changes, and pointer-leave restoration through one formatter so dollar and percentage values cannot drift apart.
