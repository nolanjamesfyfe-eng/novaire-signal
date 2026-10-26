---
tags: [signal, collapsed-cards, geometry, scoped-css]
---
# Nine compact closed cards

The approved set is Latest, Weekly Asymmetry, Catalysts, Fed, Polymarket,
Alpaca, Thailand, Economies, and Daily Tasks. Only their closed shells and
outer summary alignment are changed. Do not propagate these dimensions to
nested disclosures or expanded content.

`compact-closed.css` is embedded by `generate.py` into the main output.
The 38 CSS-pixel summary matches the existing Fed desktop baseline exactly:
43.796875 rendered outer pixels after existing body zoom and borders.
A font-relative container query switches narrow/text-enlarged cards to a
shared wrapping summary height. All icons own an equal 1rem column, followed
by the existing 8px title gap. Keep title fonts, glyphs, and chevron intact.

Run `tests/compact-closed-geometry.cjs` with NOVAIRE_SIGNAL_BASE_URL and
QA_OUTPUT_DIR. On this host, Snap Chromium needs TMPDIR pointing at the
worktree's `.playwright-tmp` rather than the hidden Hermes scratch directory.
The regression exercises all nine closed heights and icon/title x offsets,
summary text-range containment, chevron size, keyboard opening, click closing,
reload persistence, and expanded Latest rows at 1440/1920/320/360/390 and 200%
text. `tests/fed-mobile-geometry.cjs` protects the expanded Fed layout.

Baseline f35c2b49 has only **two** Latest rows (Instagram and Ink), despite
historical tests expecting six. Preserve baseline content; do not fabricate
or restore feeds during a spacing-only correction. The pre-existing render
suite has 12 failures; comparison against the unchanged baseline established
that none were introduced by this correction. All script blocks and accordion
body HTML were compared byte-for-byte against that baseline before release.

For equal cards, measure rendered boxes, not padding declarations. A leftover
explicit closed `height`/`min-height` on Thailand survived zero-padding until
explicitly reset. Prefer font-relative container queries over viewport-only
breakpoints so 200% text on desktop also gets a wrapped layout.
