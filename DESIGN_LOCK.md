# Novaire Signal — Approved Design Lock

**Baseline approved by Novaire:** 2026-08-16  
**Status:** Locked. Do not visually redesign, restyle, substitute, or “improve” without Novaire’s explicit approval.

## What may change without design approval

- Live prices, portfolio values, dates, news, quotes, recommendations, countdown values, and other dynamic content.
- Data-source fixes, reliability fixes, accessibility fixes, and security fixes that do not alter the approved appearance.
- New content explicitly requested by Novaire, styled inside the existing visual system.

## What is locked

- Overall black/noir page appearance and narrow `720px` content column.
- Antique-gold, ivory, muted lavender-grey, and near-black palette.
- Inter body typography and Cormorant Garamond editorial/display typography.
- Card backgrounds, borders, spacing, corner radius, headings, and divider treatment.
- Current header/footer wordmark size, spacing, italic gold `Signal`, and tagline treatment.
- Current section order and layout unless Novaire explicitly requests a structural change.
- Existing mobile behavior.

## Signal bolt — immutable brand asset

- Use the exact traced high-voltage silhouette approved from Novaire’s supplied image.
- Fixed antique gold: `#b59662`.
- Preserve the displayed size and alignment beside `Signal`.
- Deterministic inline SVG with `fill: currentColor`.
- Exactly two instances on the main page: header and footer.
- Never substitute a Unicode emoji, Font Awesome/generic bolt, alternate SVG, recolor filter, glow, or drop shadow.

Canonical path:

```svg
M219 44Q217 43 215 44L51 180Q49 183 51 185Q53 187 56 187L130 186Q132 186 132 188L72 289Q70 293 73 295Q76 297 83 291L239 155Q241 153 239 149Q238 147 236 147L166 148Q162 148 160 146L219 51Q222 46 219 44Z
```

## Enforcement

- `scripts/verify-build.js` blocks deployment when core design markers or the approved bolt change.
- `tests/test_render_contracts.py` independently enforces the bolt’s path, color, dimensions, count, and lack of emoji/filter regressions.
- Updating either guard requires Novaire’s explicit approval for the corresponding visual change.
