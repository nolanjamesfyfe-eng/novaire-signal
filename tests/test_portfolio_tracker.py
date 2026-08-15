import unittest
from datetime import datetime, timezone

import portfolio_tracker


class PortfolioTrackerTests(unittest.TestCase):
    def test_parse_kraken_live_total_from_authoritative_sheet_row(self):
        rows = [
            ["NOTES", "", "Description", "Name", "Exchange", "52w L", "off 52 w L ^", "BUY Price $", "# of CON", "Imargin * Contracts", "Value of fund", "% of Fund", "$ ROI", "ROI %", "CAD"],
            ["", "", "", "", "", "", "", "", "", "", "$1,000", "Live", "", "", "1.38765003"],
            ["", "", "", "", "", "", "", "", "", "Oct 2025", "$7,000", "Inception", "-$6,000.00", "-85.71%", ""],
        ]

        result = portfolio_tracker.parse_kraken_rows(rows)

        self.assertEqual(result["total_usd"], 1000.0)
        self.assertAlmostEqual(result["usdcad"], 1.38765003)
        self.assertAlmostEqual(result["total_cad"], 1387.65003)
        self.assertEqual(result["sheet_gid"], "338118850")

    def test_market_close_date_uses_latest_completed_new_york_session(self):
        saturday_utc = datetime(2026, 8, 15, 8, 0, tzinfo=timezone.utc)
        tuesday_before_close_utc = datetime(2026, 8, 18, 15, 0, tzinfo=timezone.utc)
        tuesday_after_close_utc = datetime(2026, 8, 18, 21, 0, tzinfo=timezone.utc)

        self.assertEqual(portfolio_tracker.latest_completed_market_date(saturday_utc), "2026-08-14")
        self.assertEqual(portfolio_tracker.latest_completed_market_date(tuesday_before_close_utc), "2026-08-17")
        self.assertEqual(portfolio_tracker.latest_completed_market_date(tuesday_after_close_utc), "2026-08-18")

    def test_period_model_uses_latest_snapshot_on_or_before_target(self):
        history = {
            "snapshots": [
                {"market_date": "2025-08-14", "accounts": {"tfsa_ws": {"cad": 100000.0}}},
                {"market_date": "2026-05-14", "accounts": {"tfsa_ws": {"cad": 110000.0}}},
                {"market_date": "2026-07-15", "accounts": {"tfsa_ws": {"cad": 115000.0}}},
                {"market_date": "2026-08-07", "accounts": {"tfsa_ws": {"cad": 119000.0}}},
                {"market_date": "2026-08-13", "accounts": {"tfsa_ws": {"cad": 120000.0}}},
                {"market_date": "2026-08-14", "accounts": {
                    "tfsa_ws": {"cad": 121390.06},
                    "kraken": {"cad": 1387.65, "usd": 1000.0},
                }},
            ]
        }

        model = portfolio_tracker.build_tracker_model(history)

        self.assertAlmostEqual(model["current_total_cad"], 122777.71, places=2)
        self.assertAlmostEqual(model["accounts"]["tfsa_ws"]["periods"]["1D"]["amount"], 1390.06, places=2)
        self.assertAlmostEqual(model["accounts"]["tfsa_ws"]["periods"]["1W"]["amount"], 2390.06, places=2)
        self.assertAlmostEqual(model["accounts"]["tfsa_ws"]["periods"]["3M"]["amount"], 11390.06, places=2)
        self.assertAlmostEqual(model["accounts"]["tfsa_ws"]["periods"]["1Y"]["amount"], 21390.06, places=2)
        self.assertIsNone(model["accounts"]["kraken"]["periods"]["1D"])
        self.assertIsNone(model["combined_periods"]["1D"])

    def test_render_tracker_has_two_accounts_and_all_periods(self):
        history = {"snapshots": [{
            "market_date": "2026-08-14",
            "captured_at_utc": "2026-08-15T08:00:00+00:00",
            "accounts": {
                "tfsa_ws": {"cad": 121390.06, "usd": 87478.87},
                "kraken": {"cad": 1387.65, "usd": 1000.0},
            },
        }]}

        html = portfolio_tracker.render_tracker_html(portfolio_tracker.build_tracker_model(history))

        self.assertIn('id="net-worth-tracker"', html)
        self.assertIn("Net Worth Tracker", html)
        self.assertIn("Wealthsimple TFSA", html)
        self.assertIn("Kraken", html)
        for label in ("1D", "1W", "1M", "3M", "1Y"):
            self.assertIn(f">{label}<", html)
        self.assertIn("C$122,778", html)
        self.assertIn("History started", html)


if __name__ == "__main__":
    unittest.main()
