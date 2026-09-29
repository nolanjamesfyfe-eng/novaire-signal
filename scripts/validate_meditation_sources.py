#!/usr/bin/env python3
"""Validate reviewed meditation expansion provenance without shipping source books."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
corpus = json.loads((ROOT / "data/meditations.json").read_text())["entries"]
review = json.loads((ROOT / "data/meditations-expansion-review.json").read_text())["entries"]
sources = json.loads((ROOT / "data/meditations-sources.json").read_text())["sources"]
by_id = {item["id"]: item for item in corpus}
source_keys = {(item["author"], item["work"], item["url"]) for item in sources}
for row in review:
    item = by_id[row["id"]]
    assert item["text"] == row["text"]
    assert hashlib.sha256(item["text"].encode()).hexdigest() == item["evidenceHash"]
    assert item["sourceAnchor"].startswith("sentence-")
    assert (item["author"], item["work"], item["sourceUrl"]) in source_keys
    assert row["reviewStatus"] == "retained"
print(f"validated {len(review)} reviewed expansion excerpts across {len(source_keys)} public-domain editions")
