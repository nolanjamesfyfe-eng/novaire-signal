"""Deterministic, durable Daily Meditation selection."""
from __future__ import annotations

import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

MIN_GAP_DAYS = 183
WINDOW_DAYS = 365
MAX_IN_WINDOW = 2


def stable_hash(value: str) -> int:
    result = 2166136261
    for char in value:
        result = ((result ^ ord(char)) * 16777619) & 0xFFFFFFFF
    return result


def balanced_cycle(entries: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in entries:
        groups[item["author"]].append(item)
    for items in groups.values():
        items.sort(key=lambda item: stable_hash(item["id"]))
    ordered: list[dict] = []
    while any(groups.values()):
        previous = ordered[-1] if ordered else None
        authors = [
            (author, items) for author, items in groups.items()
            if items and (not previous or author != previous["author"])
        ]
        if not authors:  # only one author remains; mathematically unavoidable
            authors = [(author, items) for author, items in groups.items() if items]
        authors.sort(key=lambda pair: (-len(pair[1]), stable_hash(f"{pair[0]}:{len(ordered)}")))
        chosen = None
        for _, items in authors:
            chosen = next((item for item in items if not previous or item["theme"] != previous["theme"]), None)
            if chosen:
                break
        chosen = chosen or authors[0][1][0]
        ordered.append(chosen)
        groups[chosen["author"]].remove(chosen)
    return ordered


def select_quote(entries: list[dict], edition: str, history: dict[str, str], prior_seen: set[str] | None = None) -> dict:
    by_id = {item["id"]: item for item in entries}
    if edition in history and history[edition] in by_id:
        return by_id[history[edition]]
    day = date.fromisoformat(edition)
    appearances: dict[str, list[date]] = defaultdict(list)
    prior_authors: list[str] = []
    prior_themes: list[str] = []
    for key, quote_id in sorted(history.items()):
        try:
            seen_day = date.fromisoformat(key)
        except ValueError:
            continue
        if seen_day >= day or quote_id not in by_id:
            continue
        appearances[quote_id].append(seen_day)
        prior_authors.append(by_id[quote_id]["author"])
        prior_themes.append(by_id[quote_id]["theme"])
    cycle = balanced_cycle(entries)
    rank = {item["id"]: i for i, item in enumerate(cycle)}
    offset = (day - date(1970, 1, 1)).days % len(cycle)
    last_author = prior_authors[-1] if prior_authors else None
    last_theme = prior_themes[-1] if prior_themes else None
    prior_seen = prior_seen or set()

    def eligible(item: dict) -> bool:
        dates = appearances[item["id"]]
        if dates and (day - dates[-1]).days < MIN_GAP_DAYS:
            return False
        return sum(0 < (day - d).days <= WINDOW_DAYS for d in dates) < MAX_IN_WINDOW

    candidates = [item for item in cycle if eligible(item)]
    if not candidates:
        raise RuntimeError("No quote satisfies the rolling-window rotation constraints")

    def score(item: dict) -> tuple:
        dates = appearances[item["id"]]
        recent_count = sum(0 < (day - d).days <= WINDOW_DAYS for d in dates)
        # New reviewed material precedes the undated legacy set; this does not invent history.
        legacy_penalty = item["id"] in prior_seen
        author_repeat = item["author"] == last_author
        theme_repeat = item["theme"] == last_theme
        cyclic_rank = (rank[item["id"]] - offset) % len(cycle)
        return (len(dates), recent_count, legacy_penalty, author_repeat, theme_repeat, cyclic_rank, item["id"])

    return min(candidates, key=score)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def select_for_edition(corpus_path: Path, history_path: Path, prior_seen_path: Path, edition: str, record: bool = False) -> dict:
    entries = load_json(corpus_path, {"entries": []})["entries"]
    history = load_json(history_path, {"editions": {}})["editions"]
    prior_seen = set(load_json(prior_seen_path, {"quoteIds": []})["quoteIds"])
    selected = select_quote(entries, edition, history, prior_seen)
    if record and edition not in history:
        history[edition] = selected["id"]
        payload = json.dumps({"editions": dict(sorted(history.items()))}, indent=2) + "\n"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=history_path.name, dir=history_path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, history_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return selected
