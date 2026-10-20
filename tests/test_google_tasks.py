import json
from pathlib import Path
from unittest.mock import patch

import google_tasks


class FakeClient:
    @staticmethod
    def list_tasklists():
        return [
            {"id": "default-id", "title": "My Tasks"},
            {"id": "daily-id", "title": "Daily"},
            {"id": "monthly-id", "title": "Monthly"},
            {"id": "fashion-id", "title": "Fashion: To Buy"},
        ]

    @staticmethod
    def list_tasks(tasklist_id, show_completed, show_hidden):
        assert tasklist_id == "daily-id"
        assert show_completed is False
        assert show_hidden is False
        return [
            {"id": "private-1", "title": "First", "notes": "private", "status": "needsAction"},
            {"id": "private-2", "title": "Completed", "status": "completed"},
            {"id": "private-3", "title": "Second", "status": "needsAction"},
            {"id": "private-4", "title": "Third", "status": "needsAction"},
            {"id": "private-5", "title": "Fourth", "status": "needsAction"},
            {"id": "private-6", "title": "Fifth", "status": "needsAction"},
            {"id": "private-7", "title": "Sixth", "status": "needsAction"},
        ]


class FakePagedClient:
    calls = []

    @classmethod
    def _req(cls, method, path):
        cls.calls.append((method, path))
        if path == "/users/@me/lists?maxResults=100":
            return {"items": [{"id": "default-id", "title": "My Tasks"}], "nextPageToken": "lists-2"}
        if path == "/users/@me/lists?maxResults=100&pageToken=lists-2":
            return {"items": [{"id": "daily-id", "title": "Daily"}]}
        if path == "/lists/daily-id/tasks?showCompleted=false&showHidden=false&maxResults=100":
            return {
                "items": [
                    {"id": "deleted", "title": "Deleted", "status": "needsAction", "deleted": True},
                    {"id": "hidden", "title": "Hidden", "status": "needsAction", "hidden": True},
                    {"id": "complete", "title": "Complete", "status": "completed"},
                    {"id": "one", "title": "One", "status": "needsAction"},
                    {"id": "two", "title": "Two", "status": "needsAction"},
                ],
                "nextPageToken": "tasks-2",
            }
        if path == "/lists/daily-id/tasks?showCompleted=false&showHidden=false&maxResults=100&pageToken=tasks-2":
            return {
                "items": [
                    {"id": "three", "title": "Three", "status": "needsAction"},
                    {"id": "four", "title": "Four", "status": "needsAction"},
                    {"id": "five", "title": "Five", "status": "needsAction"},
                    {"id": "six", "title": "Six", "status": "needsAction"},
                ]
            }
        raise AssertionError(path)


def test_fetch_uses_explicit_daily_list_and_preserves_api_order():
    with patch.object(google_tasks, "_load_tasks_client", return_value=FakeClient):
        result = google_tasks.fetch_daily_snapshot(Path("unused"))
    assert result["list_title"] == "Daily"
    assert result["tasks"] == ["First", "Second", "Third", "Fourth", "Fifth"]
    serialized = json.dumps(result)
    assert "private-" not in serialized
    assert "notes" not in serialized


def test_fetch_paginates_filters_non_pending_items_and_refills_five():
    FakePagedClient.calls = []
    with patch.object(google_tasks, "_load_tasks_client", return_value=FakePagedClient):
        result = google_tasks.fetch_daily_snapshot(Path("unused"))
    assert result["tasks"] == ["One", "Two", "Three", "Four", "Five"]
    assert len(FakePagedClient.calls) == 4
    serialized = json.dumps(result).lower()
    for private_marker in ("deleted", "hidden", "complete", '"id"'):
        assert private_marker not in serialized


def test_refresh_failure_returns_cache_with_honest_state(tmp_path):
    cache = tmp_path / "tasks.json"
    cache.write_text(json.dumps({
        "list_title": "Daily",
        "tasks": ["Known task"],
        "fetched_at": "2026-10-18T01:00:00Z",
    }))
    with patch.object(google_tasks, "fetch_daily_snapshot", side_effect=RuntimeError("offline")):
        result = google_tasks.refresh_daily_tasks(cache, tmp_path / "missing")
    assert result["tasks"] == ["Known task"]
    assert result["refresh_state"] == "cached"
    assert result["fetched_at"] == "2026-10-18T01:00:00Z"


def test_refresh_without_cache_fails_closed(tmp_path):
    with patch.object(google_tasks, "fetch_daily_snapshot", side_effect=RuntimeError("offline")):
        result = google_tasks.refresh_daily_tasks(tmp_path / "missing.json", tmp_path / "missing")
    assert result["tasks"] == []
    assert result["refresh_state"] == "unavailable"
    assert result["fetched_at"] is None
