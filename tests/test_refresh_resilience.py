from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_live_freshness", ROOT / "scripts" / "verify_live_freshness.py"
)
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class RefreshResilienceTests(unittest.TestCase):
    def test_bangkok_date_marker_is_timezone_aware(self):
        # 18:30 UTC is already the next calendar day in Bangkok.
        instant = datetime(2026, 9, 1, 18, 30, tzinfo=timezone.utc)
        self.assertEqual(VERIFY.expected_label(instant), "Wednesday, September 2, 2026")

    def test_freshness_requires_exact_current_date_marker(self):
        expected = "Wednesday, September 2, 2026"
        self.assertTrue(VERIFY.is_fresh_html(f"<p>{expected}</p>", expected))
        self.assertFalse(VERIFY.is_fresh_html("<p>Tuesday, September 1, 2026</p>", expected))

    def test_refresh_script_has_lock_retries_state_and_live_verification(self):
        script = (ROOT / "scripts" / "refresh_signal.sh").read_text()
        for marker in (
            "flock -n",
            "retry 3 90 'generation and quote validation'",
            "novaire-signal-refresh-state.json",
            "verify_live_freshness.py",
            "LOCAL_HEAD",
            "REMOTE_HEAD",
        ):
            self.assertIn(marker, script)
        self.assertNotIn("git push origin main || true", script)
        self.assertNotIn("git pull --rebase --autostash origin main || true", script)

    def test_watchdog_self_repairs_stale_signal(self):
        watchdog = (ROOT / "scripts" / "watchdog_signal.sh").read_text()
        self.assertIn("--attempts 1", watchdog)
        self.assertIn("scripts/refresh_signal.sh", watchdog)
        self.assertIn("WATCHDOG repaired", watchdog)


if __name__ == "__main__":
    unittest.main()
