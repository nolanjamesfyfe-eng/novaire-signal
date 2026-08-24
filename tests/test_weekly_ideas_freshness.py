import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import generate


class WeeklyIdeasFreshnessTests(unittest.TestCase):
    def _load(self, current, history, now=datetime(2026, 8, 24, 7, 0, tzinfo=generate.BKK_TZ)):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ideas_path = root / "weekly_ideas.json"
            history_path = root / "weekly_ideas_history.json"
            ideas_path.write_text(json.dumps(current), encoding="utf-8")
            history_path.write_text(json.dumps({"candidates": history}), encoding="utf-8")
            return generate.load_weekly_ideas(now, str(ideas_path), str(history_path))

    def test_repeated_symbol_fails_closed_to_empty_current_edition(self):
        result = self._load(
            {"as_of": "2026-08-24", "ideas": [{"symbol": "NIGHT", "name": "Midnight Network"}]},
            [{"symbol": "NIGHT", "name": "Midnight"}],
        )
        self.assertEqual(result["as_of"], "2026-08-24")
        self.assertEqual(result["ideas"], [])
        self.assertIn("No new non-duplicate", result["portfolio_note"])

    def test_renamed_same_project_domain_fails_closed(self):
        result = self._load(
            {"as_of": "2026-08-24", "ideas": [{"symbol": "NEW", "name": "Midnight Protocol", "source_url": "https://midnight.network/new"}]},
            [{"symbol": "NIGHT", "name": "Midnight Network", "aliases": ["midnight.network"]}],
        )
        self.assertEqual(result["ideas"], [])

    def test_stale_edition_fails_closed_and_advances_monday_key(self):
        result = self._load(
            {"as_of": "2026-08-17", "ideas": [{"symbol": "FRESH", "name": "Fresh Asset"}]},
            [],
        )
        self.assertEqual(result["as_of"], "2026-08-24")
        self.assertEqual(result["ideas"], [])

    def test_genuinely_new_current_monday_candidate_passes(self):
        current = {
            "as_of": "2026-08-24",
            "portfolio_note": "New slate.",
            "ideas": [{"symbol": "FRESH", "name": "Fresh Asset", "source_url": "https://fresh.example/asset"}],
        }
        self.assertEqual(self._load(current, [{"symbol": "OLD", "name": "Old Asset"}]), current)


if __name__ == "__main__":
    unittest.main()
