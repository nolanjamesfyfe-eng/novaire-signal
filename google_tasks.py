#!/usr/bin/env python3
"""Read the top incomplete items from the explicit Google Tasks `Daily` list.

Only task titles are persisted for public rendering. Task IDs and notes never leave
the Google Tasks client. If refresh fails, the last successful snapshot is returned
with an explicit cached status so stale data is never presented as freshly synced.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "google_tasks_cache.json"
TASKS_CLIENT_DIR = Path(os.environ.get("GOOGLE_TASKS_CLIENT_DIR", "/root/clawd/gtasks"))
LIST_TITLE = "Daily"
MAX_TASKS = 5


def _validated_snapshot(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or payload.get("list_title") != LIST_TITLE:
        return None
    titles = payload.get("tasks")
    if not isinstance(titles, list) or len(titles) > MAX_TASKS:
        return None
    if any(not isinstance(title, str) or not title.strip() for title in titles):
        return None
    fetched_at = payload.get("fetched_at")
    if not isinstance(fetched_at, str) or not fetched_at:
        return None
    return {
        "list_title": LIST_TITLE,
        "tasks": [title.strip() for title in titles],
        "fetched_at": fetched_at,
    }


def load_cache(path: Path = CACHE_PATH) -> dict[str, Any] | None:
    try:
        return _validated_snapshot(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def _load_tasks_client(client_dir: Path):
    source = client_dir / "tasks.py"
    if not source.is_file():
        raise FileNotFoundError(f"Google Tasks client not found: {source}")
    spec = importlib.util.spec_from_file_location("novaire_google_tasks_client", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("Google Tasks client could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(client_dir))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def _all_pages(client, path: str) -> list[dict[str, Any]]:
    """Read every Google Tasks page through the authenticated client."""
    items: list[dict[str, Any]] = []
    next_path = path
    while next_path:
        page = client._req("GET", next_path)
        items.extend(page.get("items") or [])
        token = page.get("nextPageToken")
        next_path = f"{path}&pageToken={quote(str(token), safe='')}" if token else ""
    return items


def fetch_daily_snapshot(client_dir: Path = TASKS_CLIENT_DIR) -> dict[str, Any]:
    """Fetch the first five incomplete Daily tasks in Google API list order."""
    client = _load_tasks_client(client_dir)
    if hasattr(client, "_req"):
        tasklists = _all_pages(client, "/users/@me/lists?maxResults=100")
    else:
        tasklists = client.list_tasklists()
    matching_lists = [item for item in tasklists if item.get("title") == LIST_TITLE]
    if len(matching_lists) != 1:
        raise RuntimeError(f"expected exactly one {LIST_TITLE!r} task list; found {len(matching_lists)}")

    # Resolve the named list and page until five genuinely pending tasks remain.
    # IDs, notes and all other private fields are discarded before persistence.
    if hasattr(client, "_req"):
        list_id = quote(str(matching_lists[0]["id"]), safe="")
        items = _all_pages(
            client,
            f"/lists/{list_id}/tasks?showCompleted=false&showHidden=false&maxResults=100",
        )
    else:
        items = client.list_tasks(
            matching_lists[0]["id"],
            show_completed=False,
            show_hidden=False,
        )
    titles = [
        str(item.get("title") or "").strip()
        for item in items
        if item.get("status") == "needsAction"
        and not item.get("deleted")
        and not item.get("hidden")
        and str(item.get("title") or "").strip()
    ][:MAX_TASKS]
    return {
        "list_title": LIST_TITLE,
        "tasks": titles,
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def refresh_daily_tasks(
    cache_path: Path = CACHE_PATH,
    client_dir: Path = TASKS_CLIENT_DIR,
) -> dict[str, Any]:
    """Refresh Daily tasks, falling back honestly to a prior verified snapshot."""
    try:
        snapshot = fetch_daily_snapshot(client_dir)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(cache_path.suffix + ".tmp")
        temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(cache_path)
        return {**snapshot, "refresh_state": "synced"}
    except Exception as error:
        cached = load_cache(cache_path)
        if cached:
            return {**cached, "refresh_state": "cached", "refresh_error": str(error)}
        return {
            "list_title": LIST_TITLE,
            "tasks": [],
            "fetched_at": None,
            "refresh_state": "unavailable",
            "refresh_error": str(error),
        }


if __name__ == "__main__":
    result = refresh_daily_tasks()
    # The CLI intentionally emits only public-safe fields: titles, timestamp, state.
    print(json.dumps({key: result.get(key) for key in ("list_title", "tasks", "fetched_at", "refresh_state")}, ensure_ascii=False, indent=2))
