#!/usr/bin/env python3
"""Write the slim Quotes refresh pool derived from data/meditations.json."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def pool():
    entries = json.loads((ROOT / "data/meditations.json").read_text(encoding="utf-8"))["entries"]
    return [{"id": e["id"], "text": e["text"], "author": e["author"], "category": e.get("category") or "Philosophy"}
            for e in entries if e.get("curatedQuote") and len(e["text"]) <= 200]
def main():
    (ROOT / "data/quote-pool.json").write_text(json.dumps({"quotes": pool()}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
if __name__ == "__main__":
    main()
