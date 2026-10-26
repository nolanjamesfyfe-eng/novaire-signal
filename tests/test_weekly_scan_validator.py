import copy
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_weekly_scan", ROOT / "scripts" / "validate_weekly_scan.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
NOW = datetime(2026, 10, 26, 12, 0, tzinfo=ZoneInfo("Asia/Bangkok"))


class WeeklyScanProvenanceValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weekly = json.loads((ROOT / "weekly_ideas.json").read_text())
        cls.ledger = json.loads((ROOT / "weekly_scan_ledger.json").read_text())

    def validate(self, weekly=None, ledger=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "weekly_ideas.json").write_text(json.dumps(weekly or self.weekly))
            (root / "weekly_scan_ledger.json").write_text(json.dumps(ledger or self.ledger))
            return MODULE.validate(root, now=NOW)

    def test_current_incomplete_scan_is_truthful_and_names_blocker(self):
        result = self.validate()
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["blocked_accounts"], ["Evolution/TFSA"])
        self.assertEqual(result["candidates"], 17)

    def test_incomplete_cannot_launder_completion_or_publish_ideas(self):
        weekly = copy.deepcopy(self.weekly)
        ledger = copy.deepcopy(self.ledger)
        weekly["scan_completed_at"] = "2026-10-26T07:04:48+07:00"
        ledger["scan_completed_at"] = weekly["scan_completed_at"]
        with self.assertRaisesRegex(ValueError, "incomplete scan must have null completion"):
            self.validate(weekly=weekly, ledger=ledger)

    def test_completed_zero_candidate_scan_is_distinct_and_allowed_when_verified(self):
        weekly = copy.deepcopy(self.weekly)
        ledger = copy.deepcopy(self.ledger)
        weekly.update({
            "scan_status": "completed",
            "scan_completed_at": "2026-10-26T08:00:00+07:00",
            "status_message": "Verified scan completed; no candidates qualified.",
            "portfolio_note": "",
            "evidence": {
                "sources": ["https://example.test/structured-source"],
                "candidates_reviewed": 0,
                "public_ledger_path": "weekly_scan_ledger.json",
            },
            "ideas": [],
        })
        ledger.update({
            "scan_status": "completed",
            "scan_completed_at": weekly["scan_completed_at"],
            "universe": {"total": 0, "tokens": 0, "equities": 0},
            "outcomes": {state: 0 for state in MODULE.OUTCOME_STATES},
            "candidates": [],
            "accounts_checked": [
                {"account": account, "status": "live", "source": "verified live source"}
                for account in sorted(MODULE.EXPECTED_ACCOUNTS)
            ],
            "blockers": [],
        })
        result = self.validate(weekly=weekly, ledger=ledger)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["candidates"], 0)

    def test_completed_scan_fails_closed_on_blocked_account(self):
        weekly = copy.deepcopy(self.weekly)
        ledger = copy.deepcopy(self.ledger)
        weekly.update({
            "scan_status": "completed",
            "scan_completed_at": "2026-10-26T08:00:00+07:00",
            "evidence": {"sources": ["x"], "candidates_reviewed": 17, "public_ledger_path": "weekly_scan_ledger.json"},
        })
        ledger.update({"scan_status": "completed", "scan_completed_at": weekly["scan_completed_at"]})
        with self.assertRaisesRegex(ValueError, "blocked account provenance"):
            self.validate(weekly=weekly, ledger=ledger)

    def test_stale_monday_edition_fails_closed(self):
        weekly = copy.deepcopy(self.weekly)
        weekly["as_of"] = "2026-10-12"
        with self.assertRaisesRegex(ValueError, "weekly edition mismatch"):
            self.validate(weekly=weekly)


if __name__ == "__main__":
    unittest.main()
