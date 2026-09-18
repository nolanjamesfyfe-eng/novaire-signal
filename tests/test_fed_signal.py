from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

import fed_signal


CALENDAR = """
<div class="panel panel-default"><h3>2026 FOMC Meetings</h3>
  <div class="row fomc-meeting"><div class="fomc-meeting__month">September</div><div class="fomc-meeting__date">15-16*</div>
    <a href="/newsevents/pressreleases/monetary20260916a.htm">HTML</a></div>
  <div class="row fomc-meeting"><div class="fomc-meeting__month">October</div><div class="fomc-meeting__date">27-28</div></div>
</div>
"""
STATEMENT = """
<main><time>September 16, 2026</time><p>The Committee decided to raise the target range for the federal funds rate by 1/4 percentage point to 3-3/4 to 4 percent.</p></main>
"""


def response(text):
    result = Mock()
    result.text = text
    result.raise_for_status.return_value = None
    return result


class FedSignalTests(unittest.TestCase):
    def test_official_calendar_and_statement_are_parsed(self):
        session = Mock()
        session.get.side_effect = [response(CALENDAR), response(STATEMENT)]
        data = fed_signal.fetch_official_fed_data(session=session, today=date(2026, 9, 18))
        self.assertEqual(data["last_decision"], "September 16, 2026")
        self.assertEqual(data["last_action"], "Raised 0.25 percentage points")
        self.assertEqual(data["fed_funds_rate"], "3.75–4.00%")
        self.assertEqual(data["next_decision"], "October 28, 2026")
        self.assertEqual(session.get.call_count, 2)

    def test_failed_fetch_retains_valid_last_good_cache_byte_for_byte(self):
        with TemporaryDirectory() as directory:
            cache = Path(directory) / "fed.json"
            original = fed_signal.fetch_official_fed_data(
                session=Mock(get=Mock(side_effect=[response(CALENDAR), response(STATEMENT)])),
                today=date(2026, 9, 18),
            )
            cache.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")
            before = cache.read_bytes()
            failing = Mock()
            failing.get.side_effect = RuntimeError("offline")
            retained = fed_signal.get_fed_data(cache_path=cache, session=failing, today=date(2026, 9, 18))
            self.assertEqual(retained, original)
            self.assertEqual(cache.read_bytes(), before)

    def test_invalid_cache_fails_closed_when_fetch_fails(self):
        with TemporaryDirectory() as directory:
            cache = Path(directory) / "fed.json"
            cache.write_text('{"last_action": "guessed"}\n', encoding="utf-8")
            failing = Mock()
            failing.get.side_effect = RuntimeError("offline")
            with self.assertRaisesRegex(RuntimeError, "no valid last-good cache"):
                fed_signal.get_fed_data(cache_path=cache, session=failing, today=date(2026, 9, 18))

    def test_validator_rejects_non_fed_provenance_and_bad_range(self):
        valid = {
            "last_meeting_date": "2026-09-16",
            "last_decision": "September 16, 2026",
            "last_action": "Raised 0.25 percentage points",
            "last_action_source": "https://example.com/monetary20260916a.htm",
            "fed_funds_rate": "4.00–3.75%",
            "next_meeting_date": "2026-10-28",
            "next_decision": "October 28, 2026",
            "calendar_source": fed_signal.CALENDAR_URL,
            "verified_at": "2026-09-18T00:00:00Z",
        }
        with self.assertRaises(ValueError):
            fed_signal.validate_fed_cache(valid, today=date(2026, 9, 18))

    def test_refresh_script_validates_fed_before_commit(self):
        script = (Path(__file__).resolve().parents[1] / "scripts" / "refresh_signal.sh").read_text()
        self.assertLess(script.index("scripts/validate_fed_signal.py"), script.index('STAGE="commit"'))
        self.assertIn("fed_signal_cache.json", script)


if __name__ == "__main__":
    unittest.main()
