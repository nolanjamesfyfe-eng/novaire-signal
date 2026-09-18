from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

import generate

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_live_freshness", ROOT / "scripts" / "verify_live_freshness.py"
)
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class RefreshResilienceTests(unittest.TestCase):
    def test_signal_edition_rolls_over_at_0600_bangkok(self):
        before = datetime(2026, 9, 15, 22, 59, tzinfo=timezone.utc)  # 05:59 ICT
        after = datetime(2026, 9, 15, 23, 0, tzinfo=timezone.utc)  # 06:00 ICT
        self.assertEqual(generate.daily_signal_edition(before), "2026-09-15")
        self.assertEqual(generate.daily_signal_edition(after), "2026-09-16")

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
            "verify_daily_live.cjs",
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

    def test_systemd_services_set_git_credential_home(self):
        for name in ("novaire-signal-refresh.service", "novaire-signal-watchdog.service"):
            unit = (ROOT / "systemd" / name).read_text()
            self.assertIn("Environment=HOME=/root", unit)

    def test_systemd_schedule_keeps_close_and_has_two_morning_checks(self):
        refresh = (ROOT / "systemd" / "novaire-signal-refresh.timer").read_text()
        watchdog = (ROOT / "systemd" / "novaire-signal-watchdog.timer").read_text()
        self.assertIn("06:00:00 Asia/Bangkok", refresh)
        self.assertIn("16:15:00 America/New_York", refresh)
        self.assertNotIn("07:00:00 Asia/Bangkok", refresh)
        self.assertIn("06:20:00 Asia/Bangkok", watchdog)
        self.assertIn("06:40:00 Asia/Bangkok", watchdog)


if __name__ == "__main__":
    unittest.main()
