import json
import re
import unittest
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from meditation_rotation import MAX_IN_WINDOW, MIN_GAP_DAYS, WINDOW_DAYS, balanced_cycle, select_quote
from generate import daily_signal_edition

ROOT = Path(__file__).resolve().parents[1]
CORPUS = json.loads((ROOT / "data" / "meditations.json").read_text(encoding="utf-8"))
ENTRIES = CORPUS["entries"]


def normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def token_similarity(left, right):
    a, b = set(normalized(left).split()), set(normalized(right).split())
    return len(a & b) / max(1, min(len(a), len(b)))


class MeditationCorpusTests(unittest.TestCase):
    def test_schema_sources_and_reviewed_scale(self):
        self.assertIn("reviewed", CORPUS["scope"].lower())
        self.assertGreaterEqual(len(ENTRIES), 400)
        required = {"id", "author", "tradition", "work", "section", "translation", "kind", "theme", "text", "sourceUrl"}
        for entry in ENTRIES:
            self.assertEqual(entry["kind"], "excerpt")
            self.assertTrue(required <= entry.keys())
            self.assertRegex(entry["sourceUrl"], r"^https://")
            self.assertGreaterEqual(len(entry["text"]), 40)
            self.assertLessEqual(len(entry["text"]), 320)
            self.assertRegex(entry["text"], r"[.!?]$")
        counts = Counter(item["author"] for item in ENTRIES)
        self.assertGreaterEqual(counts["Marcus Aurelius"], 100)
        self.assertGreaterEqual(counts["Seneca"], 100)
        self.assertGreaterEqual(counts["Epictetus"], 100)
        self.assertGreaterEqual(counts["William James"], 80)
        self.assertGreaterEqual(counts["Carl Jung"], 20)
        self.assertGreaterEqual(counts["Will Durant"], 20)
        self.assertGreaterEqual(counts["Sigmund Freud"], 5)
        self.assertGreaterEqual(sum(item["tradition"] == "psychology" for item in ENTRIES), 85)

    def test_ids_text_containment_and_near_duplicates(self):
        ids = [entry["id"] for entry in ENTRIES]
        texts = [normalized(entry["text"]) for entry in ENTRIES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(texts), len(set(texts)))
        for i, left in enumerate(ENTRIES):
            for right in ENTRIES[i + 1:]:
                a, b = normalized(left["text"]), normalized(right["text"])
                self.assertFalse(len(a) > 50 and (a in b or b in a), (left["id"], right["id"]))
                self.assertLess(token_similarity(a, b), 0.76, (left["id"], right["id"]))

    def test_cycle_is_balanced_without_adjacent_author_or_theme(self):
        ordered = balanced_cycle(ENTRIES)
        self.assertEqual(len(ordered), len({entry["id"] for entry in ordered}))
        for left, right in zip(ordered, ordered[1:]):
            self.assertNotEqual(left["author"], right["author"])
            self.assertNotEqual(left["theme"], right["theme"])

    def test_three_year_simulation_proves_rolling_limit_and_full_cycle(self):
        history = {}
        selections = []
        start = date(2025, 12, 1)
        simulation_days = len(ENTRIES) * 3
        for offset in range(simulation_days):
            edition = (start + timedelta(days=offset)).isoformat()
            selected = select_quote(ENTRIES, edition, history)
            self.assertEqual(selected["id"], select_quote(ENTRIES, edition, history)["id"])
            history[edition] = selected["id"]
            selections.append((start + timedelta(days=offset), selected))
        # Every corpus cycle completes before any ID repeats.
        self.assertEqual(len({item["id"] for _, item in selections[:len(ENTRIES)]}), len(ENTRIES))
        positions = defaultdict(list)
        for day, item in selections:
            positions[item["id"]].append(day)
        self.assertGreaterEqual(min((b - a).days for days in positions.values() for a, b in zip(days, days[1:])), len(ENTRIES) - 1)
        measured_max = 0
        for index, (day, _) in enumerate(selections):
            window = [item["id"] for seen, item in selections[:index + 1] if 0 <= (day - seen).days < WINDOW_DAYS]
            measured_max = max(measured_max, max(Counter(window).values()))
        self.assertLessEqual(measured_max, MAX_IN_WINDOW)
        self.assertEqual(measured_max, 1)

    def test_year_boundary_pool_edit_restart_and_author_change(self):
        history = {}
        start = date(2026, 12, 20)
        for offset in range(430):
            day = start + timedelta(days=offset)
            pool = [dict(item) for item in ENTRIES]
            if offset >= 180:
                pool = pool[12:]  # remove IDs after history exists
                pool[0]["author"] = "Epictetus (edited label)"  # metadata edit must not reset ID history
            selected = select_quote(pool, day.isoformat(), dict(history))  # restart: reconstructed state only
            history[day.isoformat()] = selected["id"]
        by_id = defaultdict(list)
        for day, quote_id in history.items():
            by_id[quote_id].append(date.fromisoformat(day))
        for days in by_id.values():
            days.sort()
            for left, right in zip(days, days[1:]):
                self.assertGreaterEqual((right - left).days, MIN_GAP_DAYS)
            for day in days:
                self.assertLessEqual(sum(0 <= (day - seen).days < WINDOW_DAYS for seen in days), MAX_IN_WINDOW)

    def test_bangkok_edition_boundary_is_06_and_same_intraday(self):
        before = datetime(2026, 1, 1, 22, 59, tzinfo=timezone.utc)  # 05:59 Bangkok
        after = datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc)    # 06:00 Bangkok
        self.assertEqual(daily_signal_edition(before), "2026-01-01")
        self.assertEqual(daily_signal_edition(after), "2026-01-02")
        history = {}
        first = select_quote(ENTRIES, "2026-01-02", history)
        self.assertEqual(first["id"], select_quote(ENTRIES, "2026-01-02", history)["id"])


if __name__ == "__main__":
    unittest.main()
