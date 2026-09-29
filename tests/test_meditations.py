import json
import re
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = json.loads((ROOT / "data" / "meditations.json").read_text(encoding="utf-8"))
ENTRIES = CORPUS["entries"]


def stable_hash(value):
    result = 2166136261
    for char in value:
        result = ((result ^ ord(char)) * 16777619) & 0xFFFFFFFF
    return result


def schedule(entries):
    groups = {}
    for item in entries:
        groups.setdefault(item["author"], []).append(item)
    for items in groups.values():
        items.sort(key=lambda item: stable_hash(item["id"]))
    ordered = []
    while any(groups.values()):
        previous = ordered[-1] if ordered else None
        authors = [(author, items) for author, items in groups.items() if items and (not previous or author != previous["author"])]
        authors.sort(key=lambda pair: (-len(pair[1]), stable_hash(f"{pair[0]}:{len(ordered)}")))
        chosen = None
        for _, items in authors:
            chosen = next((item for item in items if not previous or item["theme"] != previous["theme"]), None)
            if chosen:
                break
        if not chosen:
            chosen = authors[0][1][0]
        ordered.append(chosen)
        groups[chosen["author"]].remove(chosen)
    return ordered


class MeditationCorpusTests(unittest.TestCase):
    def test_schema_sources_and_scope(self):
        self.assertIn("curated", CORPUS["scope"].lower())
        self.assertGreaterEqual(len(ENTRIES), 35)
        required = {"id", "author", "tradition", "work", "section", "kind", "theme", "text", "sourceUrl"}
        for entry in ENTRIES:
            self.assertTrue(required <= entry.keys())
            self.assertIn(entry["kind"], {"excerpt", "reflection"})
            self.assertRegex(entry["sourceUrl"], r"^https://")

    def test_ids_and_normalized_text_are_unique(self):
        ids = [entry["id"] for entry in ENTRIES]
        normalized = [re.sub(r"[^a-z0-9]+", " ", entry["text"].lower()).strip() for entry in ENTRIES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(normalized), len(set(normalized)))

    def test_cycle_has_no_reuse_and_no_adjacent_author_or_theme(self):
        ordered = schedule(ENTRIES)
        self.assertEqual(len(ordered), len({entry["id"] for entry in ordered}))
        for left, right in zip(ordered, ordered[1:]):
            self.assertNotEqual(left["author"], right["author"])
            self.assertNotEqual(left["theme"], right["theme"])

    def test_months_are_stable_and_repeat_only_after_full_cycle(self):
        ordered = schedule(ENTRIES)
        start = date(2026, 1, 1)
        selected = [ordered[((start + timedelta(days=i)) - date(1970, 1, 1)).days % len(ordered)] for i in range(365)]
        for offset in range(len(ordered), len(selected)):
            self.assertNotIn(selected[offset]["id"], {item["id"] for item in selected[offset-len(ordered)+1:offset]})
        self.assertEqual(selected[0]["id"], selected[len(ordered)]["id"])

    def test_stoicism_and_psychology_both_rotate(self):
        first_month = schedule(ENTRIES)[:30]
        counts = {tradition: sum(item["tradition"] == tradition for item in first_month) for tradition in ("stoicism", "psychology")}
        self.assertGreaterEqual(counts["psychology"], 6)
        self.assertGreaterEqual(counts["stoicism"], 18)


if __name__ == "__main__":
    unittest.main()
