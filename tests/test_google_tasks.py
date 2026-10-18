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


def test_fetch_uses_explicit_daily_list_and_preserves_api_order():
    with patch.object(google_tasks, "_load_tasks_client", return_value=FakeClient):
        result = google_tasks.fetch_daily_snapshot(Path("unused"))
    assert result["list_title"] == "Daily"
    assert result["tasks"] == ["First", "Second", "Third", "Fourth", "Fifth"]
    serialized = json.dumps(result)
    assert "private-" not in serialized
    assert "notes" not in serialized


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
