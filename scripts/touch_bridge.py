#!/usr/bin/env python3
"""Phone "Desktop site" bridge for Signal companion pages.

Android Chrome in Desktop-site mode ignores the viewport meta and lays pages out
at ~980 CSS px, shrinking everything to half size on a phone. The original
homepage reconstructs its ~490px mobile canvas with
`@media (hover:none) and (min-width:601px) and (max-width:1100px){body{zoom:2}}`.

This module applies the same contract to every companion page by rewriting
page-specific media preludes (idempotently):
  * mobile rules `(max-width:M)` with M >= 490 also fire on the bridge;
  * desktop rules `(min-width:N)` with 490 < N <= 1100 stop firing on the bridge.
Brand/shell rules are never rewritten: the canonical brand row stays identical
to the homepage, which itself is never touched.
"""
from __future__ import annotations
import re

BRIDGE = "(hover:none) and (min-width:601px) and (max-width:1100px)"
EFFECTIVE = 490  # 980px layout / zoom 2
PHONE_MIN = 400  # bridge is a phone: phone-class max-width rules (>=400px) apply too
SKIP_TOKENS = ("signal-brand-row", "signal-gate", "signal-map-icon", "signal-bolt-icon")
_W = re.compile(r"\(\s*(min|max)-width\s*:\s*([\d.]+)px\s*\)")


def _rewrite_query(q: str) -> str:
    q = q.strip()
    if "hover" in q or "pointer" in q:
        return q  # author already targets input type explicitly
    widths = {k: float(v) for k, v in _W.findall(q)}
    n, m = widths.get("min"), widths.get("max")
    if n is not None and EFFECTIVE < n <= 1100:
        return ", ".join(f"{q} and {extra}" for extra in ("(hover:hover)", "(max-width:600px)", "(min-width:1101px)"))
    if m is not None and m >= PHONE_MIN and (n is None or n <= EFFECTIVE):
        rest = [t.strip() for t in re.split(r"\band\b", _W.sub("", q)) if t.strip()]
        return ", ".join([q, " and ".join(rest + [BRIDGE])])
    return q


def rewrite_prelude(prelude: str) -> str:
    if BRIDGE in prelude or "(hover:hover)" in prelude:
        return prelude
    parts = [p for p in prelude.split(",")]
    out = [_rewrite_query(p) for p in parts]
    return ", ".join(out)


def _block_end(css: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(css)):
        c = css[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(css) - 1


def bridge_css(css: str) -> str:
    out, i = [], 0
    for mt in re.finditer(r"@media\b", css):
        if mt.start() < i:
            continue  # nested inside an already-copied block
        brace = css.find("{", mt.end())
        if brace < 0:
            break
        end = _block_end(css, brace)
        prelude = css[mt.end():brace]
        body = css[brace:end + 1]
        out.append(css[i:mt.start()])
        if any(t in body for t in SKIP_TOKENS):
            out.append(css[mt.start():end + 1])
        else:
            out.append("@media " + rewrite_prelude(prelude.strip()) + body)
        i = end + 1
    out.append(css[i:])
    return "".join(out)


def bridge_html(html: str) -> str:
    return re.sub(r"(<style\b[^>]*>)(.*?)(</style>)", lambda mm: mm[1] + bridge_css(mm[2]) + mm[3], html, flags=re.S)


PHONE = "(max-width:760px), " + BRIDGE
# phone-readability-v1: legible minimums for dense finance pages on phones. Mobile/touch only;
# desktop mouse layouts and the canonical brand row/footer tagline are untouched.
READABILITY_CSS = f"""
@media {PHONE}{{
body:not(.signal-companion-unzoomed) .psum-label{{font-size:11px;letter-spacing:.05em}}
body:not(.signal-companion-unzoomed) .psum-item{{padding:10px 6px}}
body:not(.signal-companion-unzoomed) .card-title{{font-size:12px;letter-spacing:.2em}}
html body:not(.signal-companion-unzoomed) .card .card-title a{{font-size:11px!important}}
body:not(.signal-companion-unzoomed) .collapse-toggle,body:not(.signal-companion-unzoomed) .collapse-toggle span{{font-size:12px}}
body:not(.signal-companion-unzoomed) .total-label,body:not(.signal-companion-unzoomed) .tracker-total-label,body:not(.signal-companion-unzoomed) .tracker-history-label{{font-size:11px}}
body:not(.signal-companion-unzoomed) .total-item>.positive,body:not(.signal-companion-unzoomed) .total-item>.negative{{font-size:12.5px!important}}
body:not(.signal-companion-unzoomed) .tracker-range{{font-size:11px}}
body:not(.signal-companion-unzoomed) .tracker-asof,body:not(.signal-companion-unzoomed) .tracker-hero-note,body:not(.signal-companion-unzoomed) .tracker-account-secondary,body:not(.signal-companion-unzoomed) .fallback-badge{{font-size:11px}}
body:not(.signal-companion-unzoomed) .tracker-account-name,body:not(.signal-companion-unzoomed) .tracker-subtitle{{font-size:12px}}
body:not(.signal-companion-unzoomed) .tracker-hero-change{{font-size:13px}}
body:not(.signal-companion-unzoomed) .allocation-kicker,body:not(.signal-companion-unzoomed) .allocation-source{{font-size:11px}}
body:not(.signal-companion-unzoomed) .legend-name,body:not(.signal-companion-unzoomed) .legend-pct{{font-size:14px}}
html body:not(.signal-companion-unzoomed) .card .sheet-snapshot-note{{font-size:12px!important;line-height:1.5}}
body:not(.signal-companion-unzoomed) .holding-note{{font-size:11.5px}}
body:not(.signal-companion-unzoomed) .ticker{{font-size:14.5px}}
body:not(.signal-companion-unzoomed) .portfolio-table td{{font-size:13px}}
body:not(.signal-companion-unzoomed) .debt-hub-kicker{{font-size:11px}}
body:not(.signal-companion-unzoomed) .debt-hub-copy p,body:not(.signal-companion-unzoomed) .debt-hub-link,body:not(.signal-companion-unzoomed) .eco-link{{font-size:13px}}
body:has(header.daily-header) .account-kicker{{font-size:11.5px}}
body:has(header.daily-header) .account-value{{font-size:16px}}
body:has(header.daily-header) .account-detail small,body:has(header.daily-header) .mover small,body:has(header.daily-header) .position small{{font-size:11px;letter-spacing:.04em}}
body:has(header.daily-header) .account-detail .source{{font-size:11px}}
body:has(header.daily-header) .position .lead{{font-size:12.5px}}
body:has(header.daily-header) .metric-sub,body:has(header.daily-header) .quote-date{{font-size:11px;line-height:1.35}}
body:has(header.daily-header) .quote-grid b,body:has(header.daily-header) .impact-grid b{{font-size:14.5px}}
body:has(header.daily-header) .periods,body:has(header.daily-header) .periods b{{font-size:12.5px}}
body:has(header.daily-header) .movers .section-label{{font-size:11px}}
body:has(header.daily-header) .mover small{{font-size:12px;line-height:1.4;letter-spacing:0}}
body:has(header.daily-header) nav[aria-label="Daily section"] a{{font-size:12px}}
body:has(header.daily-header) main>.sub{{font-size:12.5px}}
body:has(#chart) .label,body:has(#chart) .eyebrow{{font-size:11.5px}}
body:has(#chart) .back-link,body:has(#chart) .period,body:has(#chart) .legend{{font-size:12.5px}}
body:has(#chart) .tab{{font-size:13px}}
body:has(#chart) .sub,body:has(#chart) .projection-note,body:has(#chart) .row,body:has(#chart) .section-head small{{font-size:13.5px}}
body:has(#chart) .footer{{font-size:11px}}
body:has(#chart) header p{{font-size:15px}}
}}
"""

SHELL_CSS = READABILITY_CSS + f"""
/* phone-desktop-site-bridge-v1: same contract as the original homepage. Android Chrome
   Desktop-site lays out at ~980px; rebuild the ~490px mobile canvas instead of shrinking. */
@media {BRIDGE}{{html body{{zoom:2}}}}
"""
