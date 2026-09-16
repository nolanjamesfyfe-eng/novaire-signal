#!/usr/bin/env python3
"""Safely update the canonical public travel answers."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "countries.json"
VISITED = ROOT / "visited.json"


def main(args: list[str]) -> int:
    valid = {row["iso2"] for row in json.loads(CATALOG.read_text())}
    data = json.loads(VISITED.read_text())
    answers = data.setdefault("answers", {})
    if not args:
        print("Usage: python map/update_visited.py CA=true FR=false [JP=true ...]")
        return 2
    for item in args:
        try:
            raw_code, raw_value = item.split("=", 1)
        except ValueError:
            raise SystemExit(f"Invalid answer {item!r}; expected ISO2=true|false")
        code = raw_code.upper()
        if code not in valid:
            raise SystemExit(f"Unknown or non-catalog ISO2 code: {code}")
        values = {"true": True, "yes": True, "false": False, "no": False}
        if raw_value.lower() not in values:
            raise SystemExit(f"Invalid value for {code}: use true/false or yes/no")
        answers[code] = values[raw_value.lower()]
    data["answers"] = dict(sorted(answers.items()))
    data["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    VISITED.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Updated {len(args)} answer(s); {len(answers)} total recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
