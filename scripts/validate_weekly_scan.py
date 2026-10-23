#!/usr/bin/env python3
"""Fail closed on weekly scan/ledger provenance mismatches."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BANGKOK = ZoneInfo("Asia/Bangkok")
EXPECTED_ACCOUNTS = {"personal/TFSA", "RRSP", "Kraken", "Alpaca", "Evolution/TFSA"}
OUTCOME_STATES = {"qualified", "watch", "economic_rejection", "portfolio_concentration", "evidence_blocked"}


def fail(message: str) -> None:
    raise ValueError(message)


def validate(root: Path, now: datetime | None = None) -> dict:
    weekly = json.loads((root / "weekly_ideas.json").read_text(encoding="utf-8"))
    ledger = json.loads((root / "weekly_scan_ledger.json").read_text(encoding="utf-8"))
    current = (now or datetime.now(BANGKOK)).astimezone(BANGKOK)
    expected = (current.date()).fromordinal(current.date().toordinal() - current.weekday()).isoformat()

    if weekly.get("as_of") != expected or ledger.get("edition_as_of") != expected:
        fail(f"weekly edition mismatch: expected {expected}, weekly={weekly.get('as_of')}, ledger={ledger.get('edition_as_of')}")
    if weekly.get("scan_status") != ledger.get("scan_status"):
        fail("weekly data and public ledger disagree on scan_status")
    if weekly.get("scan_completed_at") != ledger.get("scan_completed_at"):
        fail("weekly data and public ledger disagree on scan_completed_at")

    candidates = ledger.get("candidates")
    universe = ledger.get("universe")
    outcomes = ledger.get("outcomes")
    if not isinstance(candidates, list) or not isinstance(universe, dict) or not isinstance(outcomes, dict):
        fail("ledger requires candidates, universe and outcomes")
    if universe.get("total") != len(candidates):
        fail("ledger universe.total does not match candidate count")
    if set(outcomes) != OUTCOME_STATES:
        fail("ledger outcome states changed or are incomplete")
    for state, declared in outcomes.items():
        actual = sum(row.get("status") == state for row in candidates)
        if declared != actual:
            fail(f"ledger outcome {state} declares {declared}, found {actual}")
    if sum(outcomes.values()) != len(candidates):
        fail("ledger outcomes do not cover every candidate exactly once")

    accounts = ledger.get("accounts_checked")
    if not isinstance(accounts, list):
        fail("ledger accounts_checked must be a list")
    account_names = {str(row.get("account")) for row in accounts if isinstance(row, dict)}
    if account_names != EXPECTED_ACCOUNTS:
        fail(f"account coverage mismatch: expected {sorted(EXPECTED_ACCOUNTS)}, got {sorted(account_names)}")
    for row in accounts:
        if row.get("status") not in {"live", "evidence_blocked"} or not str(row.get("source") or "").strip():
            fail(f"invalid account provenance row: {row!r}")

    status = weekly.get("scan_status")
    if status == "incomplete":
        if weekly.get("scan_completed_at") is not None or weekly.get("evidence") is not None or weekly.get("ideas") != []:
            fail("incomplete scan must have null completion/evidence and no ideas")
        if not any(row.get("status") == "evidence_blocked" for row in accounts):
            fail("incomplete scan must identify at least one blocked account source")
    elif status == "completed":
        if any(row.get("status") != "live" for row in accounts):
            fail("completed scan cannot contain blocked account provenance")
        evidence = weekly.get("evidence")
        if not isinstance(evidence, dict) or not evidence.get("sources") or evidence.get("candidates_reviewed") != len(candidates):
            fail("completed scan evidence must cover the full public ledger")
        if evidence.get("public_ledger_path") != "weekly_scan_ledger.json":
            fail("completed scan must bind evidence to weekly_scan_ledger.json")
        if outcomes.get("qualified") != len(weekly.get("ideas") or []):
            fail("published idea count must match qualified ledger candidates")
        completed = datetime.fromisoformat(weekly["scan_completed_at"])
        if completed.tzinfo is None or not 0 <= (completed.astimezone(BANGKOK).date() - datetime.fromisoformat(expected).date()).days <= 6:
            fail("completion timestamp is outside the Bangkok edition week")
    else:
        fail(f"unsupported scan_status: {status!r}")

    return {"ok": True, "edition": expected, "status": status, "candidates": len(candidates), "blocked_accounts": [row["account"] for row in accounts if row["status"] == "evidence_blocked"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(validate(args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
