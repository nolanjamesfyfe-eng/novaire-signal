#!/usr/bin/env python3
"""Verify that the canonical Signal page shows today's Bangkok date."""
from __future__ import annotations

import argparse
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

CANONICAL = "https://novairesignal.com/"
BANGKOK = ZoneInfo("Asia/Bangkok")


def expected_label(now: datetime | None = None) -> str:
    current = now.astimezone(BANGKOK) if now else datetime.now(BANGKOK)
    return current.strftime("%A, %B %-d, %Y")


def is_fresh_html(html: str, expected: str | None = None) -> bool:
    return (expected or expected_label()) in html


def fetch_html() -> str:
    request = urllib.request.Request(
        f"{CANONICAL}?freshness={int(time.time())}",
        headers={"Cache-Control": "no-cache", "User-Agent": "NovaireSignal-Watchdog/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"canonical page returned HTTP {response.status}")
        return response.read().decode("utf-8", "ignore")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--delay", type=int, default=20)
    args = parser.parse_args()
    wanted = expected_label()
    last_error = "date marker absent"
    for attempt in range(1, args.attempts + 1):
        try:
            if is_fresh_html(fetch_html(), wanted):
                print(f"LIVE FRESH: {wanted} (attempt {attempt}/{args.attempts})")
                return 0
            last_error = f"expected marker not found: {wanted}"
        except Exception as error:  # network/deployment propagation is retryable
            last_error = str(error)
        print(f"LIVE STALE: {last_error} (attempt {attempt}/{args.attempts})")
        if attempt < args.attempts:
            time.sleep(args.delay)
    print(f"LIVE VERIFICATION FAILED: {last_error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
