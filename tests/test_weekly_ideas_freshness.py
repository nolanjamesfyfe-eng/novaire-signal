import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import generate


class WeeklyIdeasFreshnessTests(unittest.TestCase):
    @staticmethod
    def _completed(ideas=None, as_of="2026-08-24"):
        ideas = ideas or []
        for idea in ideas:
            idea.setdefault("source_url", "https://example.com/asset")
            idea.setdefault("thesis", "Evidence-backed upside case.")
            idea.setdefault("risk", "Thesis may fail.")
            idea.setdefault("trigger", "Verified catalyst occurs.")
        return {
            "schema_version": 1,
            "as_of": as_of,
            "scan_status": "completed",
            "scan_completed_at": f"{as_of}T06:30:00+07:00",
            "status_message": "Verified completed weekly scan.",
            "portfolio_note": "Evidence-backed weekly scan.",
            "evidence": {
                "methodology": "Screened current holdings and public market sources.",
                "accounts_checked": ["personal portfolio", "Evolution Fund"],
                "sources": [{"url": "https://example.com/scan", "checked_at": f"{as_of}T06:00:00+07:00"}],
                "candidates_reviewed": 12,
            },
            "ideas": ideas,
        }

    def _load(self, current, history, now=datetime(2026, 8, 24, 7, 0, tzinfo=generate.BKK_TZ)):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ideas_path = root / "weekly_ideas.json"
            history_path = root / "weekly_ideas_history.json"
            ideas_path.write_text(json.dumps(current), encoding="utf-8")
            history_path.write_text(json.dumps({"candidates": history}), encoding="utf-8")
            return generate.load_weekly_ideas(now, str(ideas_path), str(history_path))

    def test_repeated_symbol_fails_closed_to_empty_current_edition(self):
        current = self._completed([{"symbol": "NIGHT", "name": "Midnight Network"}])
        result = self._load(
            current,
            [{"symbol": "NIGHT", "name": "Midnight"}],
        )
        self.assertEqual(result["as_of"], "2026-08-24")
        self.assertEqual(result["ideas"], [])
        self.assertEqual(result["scan_state"], "unverified")
        self.assertIn("repeated prior candidate", result["status_message"])

    def test_renamed_same_project_domain_fails_closed(self):
        result = self._load(
            self._completed([{"symbol": "NEW", "name": "Midnight Protocol", "source_url": "https://midnight.network/new"}]),
            [{"symbol": "NIGHT", "name": "Midnight Network", "aliases": ["midnight.network"]}],
        )
        self.assertEqual(result["ideas"], [])

    def test_stale_edition_preserves_real_scan_date(self):
        result = self._load(
            self._completed([{"symbol": "FRESH", "name": "Fresh Asset"}], as_of="2026-08-17"),
            [],
        )
        self.assertEqual(result["as_of"], "2026-08-17")
        self.assertEqual(result["scan_state"], "stale")
        self.assertEqual(result["ideas"], [])

    def test_genuinely_new_current_monday_candidate_passes(self):
        current = self._completed([{"symbol": "FRESH", "name": "Fresh Asset", "source_url": "https://fresh.example/asset"}])
        result = self._load(current, [{"symbol": "OLD", "name": "Old Asset"}])
        self.assertEqual(result["scan_state"], "ideas")
        self.assertEqual(result["ideas"], current["ideas"])

    def test_current_completed_empty_is_distinct_from_unverified(self):
        result = self._load(self._completed(), [])
        self.assertEqual(result["scan_state"], "completed_empty")
        self.assertEqual(result["evidence"]["candidates_reviewed"], 12)

    def test_legacy_empty_file_without_evidence_is_unverified(self):
        result = self._load(
            {"as_of": "2026-08-24", "portfolio_note": "EMPTY — none cleared.", "ideas": []},
            [],
        )
        self.assertEqual(result["as_of"], "2026-08-24")
        self.assertEqual(result["scan_state"], "unverified")
        self.assertNotIn("none cleared", result["portfolio_note"])

    def test_completed_scan_requires_provenance(self):
        current = self._completed()
        current["evidence"]["sources"] = []
        result = self._load(current, [])
        self.assertEqual(result["scan_state"], "unverified")
        self.assertIn("evidence.sources", result["status_message"])

    def test_completed_scan_timestamp_must_belong_to_edition_week(self):
        current = self._completed()
        current["scan_completed_at"] = "2026-08-31T06:30:00+07:00"
        result = self._load(current, [])
        self.assertEqual(result["scan_state"], "unverified")
        self.assertIn("edition week", result["status_message"])

    def test_published_idea_requires_decision_provenance_fields(self):
        current = self._completed([{"symbol": "FRESH", "name": "Fresh Asset", "source_url": "https://fresh.example/asset"}])
        del current["ideas"][0]["risk"]
        result = self._load(current, [])
        self.assertEqual(result["scan_state"], "unverified")
        self.assertIn("idea requires", result["status_message"])

    def test_status_copy_never_conflates_unverified_with_completed_empty(self):
        unverified = generate.weekly_scan_presentation({"scan_state": "unverified", "as_of": "2026-08-24"})
        completed = generate.weekly_scan_presentation({"scan_state": "completed_empty", "as_of": "2026-08-24"})
        stale = generate.weekly_scan_presentation({"scan_state": "stale", "as_of": "2026-08-17"})

        self.assertEqual(unverified["label"], "Scan unverified")
        self.assertIn("No zero-candidate claim", unverified["empty_message"])
        self.assertEqual(completed["label"], "Completed Aug 24")
        self.assertIn("No new candidate cleared", completed["empty_message"])
        self.assertEqual(stale["label"], "Stale · last completed Aug 17")
        self.assertNotIn("Aug 24", stale["label"])


if __name__ == "__main__":
    unittest.main()
