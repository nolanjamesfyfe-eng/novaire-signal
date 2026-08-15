#!/usr/bin/env python3
"""Seed TFSA/WS close history from versioned Google-Sheet totals in stats.json."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from portfolio_tracker import HISTORY_PATH, latest_completed_market_date, load_history, save_history


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def main() -> None:
    history = load_history(HISTORY_PATH)
    by_date = {
        item.get("market_date"): item
        for item in history.get("snapshots", [])
        if isinstance(item, dict) and item.get("market_date")
    }

    records = git_output("log", "--follow", "--format=%H|%cI", "--", "stats.json").splitlines()
    seeded = 0
    for record in reversed(records):
        commit, captured = record.split("|", 1)
        shown = subprocess.run(
            ["git", "show", f"{commit}:stats.json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if shown.returncode:
            continue
        try:
            payload = json.loads(shown.stdout)
            portfolio = payload.get("portfolio") or {}
            total_cad = portfolio.get("total_cad")
            total_usd = portfolio.get("total_usd")
            captured_at = datetime.fromisoformat(captured.replace("Z", "+00:00"))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if not isinstance(total_cad, (int, float)) or total_cad <= 0:
            continue

        market_date = latest_completed_market_date(captured_at)
        snapshot = by_date.get(market_date, {
            "market_date": market_date,
            "accounts": {},
            "source": "Google Sheet close · recovered from versioned stats.json",
        })
        snapshot["captured_at_utc"] = captured_at.isoformat()
        snapshot.setdefault("accounts", {})["tfsa_ws"] = {"cad": round(float(total_cad), 2)}
        if isinstance(total_usd, (int, float)):
            snapshot["accounts"]["tfsa_ws"]["usd"] = round(float(total_usd), 2)
        snapshot["net_worth_cad"] = round(
            sum(float(account.get("cad", 0)) for account in snapshot["accounts"].values()),
            2,
        )
        by_date[market_date] = snapshot
        seeded += 1

    history["schema_version"] = 1
    history["source"] = "Google Sheet daily closes · TFSA/WS + Kraken"
    history["snapshots"] = sorted(by_date.values(), key=lambda item: item["market_date"])[-730:]
    save_history(history, HISTORY_PATH)
    print(f"Seeded {seeded} valid revisions into {len(history['snapshots'])} market-date closes at {HISTORY_PATH}")


if __name__ == "__main__":
    main()
