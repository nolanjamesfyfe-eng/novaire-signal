#!/usr/bin/env python3
"""Block publication unless generated Fed facts match a validated official cache."""
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fed_signal import CACHE_PATH, validate_fed_cache  # noqa: E402

cache = validate_fed_cache(json.loads(CACHE_PATH.read_text(encoding="utf-8")))
html = (ROOT / "index.html").read_text(encoding="utf-8")
soup = BeautifulSoup(html, "html.parser")
card = soup.select_one("#fed-signal-card")
failures = []
if not card:
    failures.append("Fed Signal card is missing")
else:
    text = card.get_text(" ", strip=True)
    for key in ("fed_funds_rate", "last_decision", "last_action", "next_decision"):
        if cache[key] not in text:
            failures.append(f"generated Fed card does not contain cache {key}={cache[key]!r}")
for marker in (
    "grid-template-columns:.9fr 1.2fr 1.2fr 1fr",
    ".fed-fomc{padding-left:28px}",
    "@media(max-width:520px){.fed-stats{grid-template-columns:1fr 1.6fr}",
    '<span>Rate</span>',
    '<span>Last meeting</span>',
    '<span>Next FOMC</span>',
    '<span>CME FedWatch</span>',
):
    if marker not in html:
        failures.append(f"approved Fed layout marker missing: {marker}")
if failures:
    print("REFRESH BLOCKED — Fed data/layout validation failed")
    print("\n".join(f"- {failure}" for failure in failures))
    raise SystemExit(1)
print(f"Fed data/layout: ok ({cache['last_decision']} via {cache['last_action_source']})")
