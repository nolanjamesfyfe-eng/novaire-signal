import unittest
from datetime import datetime, timezone

from bs4 import BeautifulSoup

import portfolio_tracker


class PortfolioTrackerTests(unittest.TestCase):
    def test_parse_kraken_live_total_from_authoritative_sheet_row(self):
        rows = [
            ["NOTES", "", "Description", "Name", "Exchange", "52w L", "off 52 w L ^", "BUY Price $", "# of CON", "Imargin * Contracts", "Value of fund", "% of Fund", "$ ROI", "ROI %", "CAD"],
            ["", "", "", "", "", "", "", "", "", "", "$1,000", "Live", "", "", "1.38765003"],
            ["", "", "", "", "", "", "", "", "", "Oct 2025", "$7,000", "Inception", "-$6,000.00", "-85.71%", ""],
            ["10X", "USD", "SUI", "SUI", "$0.65", "", "", "$0.72", "3682", "$2,398", "SUI", "37.81%", "", "", ""],
            ["10X", "USD", "MIDNIGHT", "NIGHT", "$0.018", "", "", "$0.018", "115139", "$2,094", "BTC", "33.03%", "", "", ""],
            ["10X", "USD", "Cardano", "ADA", "$0.17", "", "", "$0.16", "8672", "$1,505", "ADA", "29.16%", "", "", ""],
        ]

        result = portfolio_tracker.parse_kraken_rows(rows)

        self.assertEqual(result["total_usd"], 1000.0)
        self.assertAlmostEqual(result["usdcad"], 1.38765003)
        self.assertAlmostEqual(result["total_cad"], 1387.65003)
        self.assertEqual(result["sheet_gid"], "338118850")
        self.assertEqual(result["inception_usd"], 7000.0)
        self.assertEqual(result["inception_label"], "Oct 2025")
        self.assertEqual(result["position_weights_pct"][0], ("SUI", 37.81))
        self.assertAlmostEqual(result["position_weight_total_pct"], 100.0)

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
        self.assertIsNone(model["accounts"]["kraken"]["periods"]["1D"])
        self.assertIsNone(model["combined_periods"]["1D"])

    def test_render_tracker_omits_unavailable_performance_rows_and_periods(self):
        history = {"snapshots": [
            {
                "market_date": "2026-08-13",
                "captured_at_utc": "2026-08-14T22:00:00+00:00",
                "accounts": {"tfsa_ws": {"cad": 120000.0, "usd": 86500.0}},
            },
            {
                "market_date": "2026-08-14",
                "captured_at_utc": "2026-08-15T08:00:00+00:00",
                "accounts": {
                    "tfsa_ws": {"cad": 121390.06, "usd": 87478.87},
                    "kraken": {"cad": 1387.65, "usd": 1000.0},
                },
            },
        ]}

        html = portfolio_tracker.render_tracker_html(portfolio_tracker.build_tracker_model(history))

        self.assertIn('id="net-worth-tracker"', html)
        self.assertIn("Net Worth Tracker", html)
        self.assertIn("Wealthsimple TFSA", html)
        self.assertIn("Kraken", html)
        self.assertIn(">1D<", html)
        self.assertIn(">YTD<", html)

        self.assertIn("C$122,778", html)
        self.assertIn("Account-value return, not pure investment return", html)
        self.assertNotIn("Building", html)
        self.assertNotIn("Total Net Worth", html)
        self.assertIn('data-range="ALL"', html)
        self.assertIn("Interactive total net worth history", html)
        soup = BeautifulSoup(html, "html.parser")
        performance_names = [node.get_text(" ", strip=True) for node in soup.select(".tracker-performance-name")]
        self.assertEqual(performance_names, ["Wealthsimple TFSA"])
        self.assertEqual(len(soup.select(".tracker-hero")), 1)

    def test_kraken_inception_reference_renders_separate_chart_and_estimated_ytd(self):
        history = {"kraken_reference": {"date": "2025-10-01", "label": "Oct 2025", "usd": 7000.0}, "snapshots": [
            {"market_date": "2026-08-14", "accounts": {"tfsa_ws": {"cad": 121000.0}, "kraken": {"cad": 1386.0, "usd": 1000.0}}}
        ]}
        model = portfolio_tracker.build_tracker_model(history)
        html = portfolio_tracker.render_tracker_html(model)
        self.assertAlmostEqual(model["accounts"]["kraken"]["periods"]["YTD"]["percent"], -85.714, places=2)
        self.assertIn("US$1,000", html)
        self.assertIn("−85.7%", html)
        self.assertIn("≈−US$6,000", html)
        self.assertIn("Account-value return, not pure investment return", html)

    def test_ytd_uses_first_verified_current_year_close_when_january_is_unavailable(self):
        history = {"snapshots": [
            {"market_date": "2026-04-10", "accounts": {"tfsa_ws": {"cad": 100000.0}}},
            {"market_date": "2026-08-14", "accounts": {"tfsa_ws": {"cad": 112500.0}}},
        ]}
        model = portfolio_tracker.build_tracker_model(history)
        ytd = model["accounts"]["tfsa_ws"]["periods"]["YTD"]
        self.assertAlmostEqual(ytd["percent"], 12.5)
        self.assertEqual(ytd["baseline_date"], "2026-04-10")
        self.assertTrue(ytd["estimated"])
        self.assertIn(">YTD<", portfolio_tracker.render_tracker_html(model))


if __name__ == "__main__":
    unittest.main()
