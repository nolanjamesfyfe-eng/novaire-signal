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

        self.assertAlmostEqual(model["current_total_cad"], 121390.06, places=2)
        self.assertAlmostEqual(model["accounts"]["tfsa_ws"]["periods"]["1D"]["amount"], 1390.06, places=2)
        self.assertAlmostEqual(model["accounts"]["tfsa_ws"]["periods"]["1W"]["amount"], 2390.06, places=2)
        self.assertAlmostEqual(model["accounts"]["tfsa_ws"]["periods"]["3M"]["amount"], 11390.06, places=2)
        self.assertNotIn("kraken", model["accounts"])
        self.assertAlmostEqual(model["combined_periods"]["1D"]["amount"], 1390.06, places=2)

    def test_closed_kraken_is_removed_from_current_snapshot_without_rewriting_history(self):
        old = {"market_date": "2026-08-13", "accounts": {"tfsa_ws": {"cad": 120000.0}, "kraken": {"cad": 1400.0}}}
        same_day = {"market_date": "2026-08-14", "accounts": {"tfsa_ws": {"cad": 121000.0}, "kraken": {"cad": 1387.65}}}
        history = {"snapshots": [old, same_day]}

        updated = portfolio_tracker.upsert_daily_snapshot(
            history,
            {"total_cad": 121390.06},
            {"total_cad": 1387.65, "total_usd": 1000.0},
            now=datetime(2026, 8, 14, 22, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(updated["snapshots"][0], old)
        self.assertEqual(updated["snapshots"][-1]["accounts"], {"tfsa_ws": {"cad": 121390.06}})
        self.assertEqual(updated["snapshots"][-1]["net_worth_cad"], 121390.06)

    def test_live_session_cannot_overwrite_prior_completed_close(self):
        prior_close = {
            "market_date": "2026-08-17",
            "captured_at_utc": "2026-08-18T01:55:00+00:00",
            "accounts": {"tfsa_ws": {"cad": 121000.0}},
            "net_worth_cad": 121000.0,
        }
        history = {"snapshots": [prior_close]}

        updated = portfolio_tracker.upsert_daily_snapshot(
            history,
            {"total_cad": 119000.0},
            {},
            # Tuesday 11:00 ET: sheet prices are live Tuesday marks, not Monday close.
            now=datetime(2026, 8, 18, 15, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(updated["snapshots"], [prior_close])

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
        self.assertNotIn("Kraken", html)
        self.assertIn("C$121,390", html)
        self.assertNotIn("Building", html)
        self.assertIn('data-range="ALL"', html)
        self.assertIn("Interactive total net worth history", html)
        soup = BeautifulSoup(html, "html.parser")
        self.assertFalse(soup.select(".tracker-performance-title, .tracker-performance, .tracker-foot"))
        self.assertNotIn("Close-to-close performance", html)
        self.assertNotIn("Account-value return, not pure investment return", html)
        self.assertEqual(
            [node.get_text(" ", strip=True) for node in soup.select(".tracker-account-name")],
            ["Wealthsimple TFSA"],
        )
        self.assertEqual(len(soup.select(".tracker-hero")), 1)

    def test_kraken_inception_reference_remains_historical_but_is_not_active(self):
        history = {"kraken_reference": {"date": "2025-10-01", "label": "Oct 2025", "usd": 7000.0}, "snapshots": [
            {"market_date": "2026-08-14", "accounts": {"tfsa_ws": {"cad": 121000.0}, "kraken": {"cad": 1386.0, "usd": 1000.0}}}
        ]}
        model = portfolio_tracker.build_tracker_model(history)
        self.assertNotIn("kraken", model["accounts"])
        self.assertEqual(history["kraken_reference"]["usd"], 7000.0)
        self.assertEqual(history["snapshots"][0]["accounts"]["kraken"]["usd"], 1000.0)

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
        self.assertNotIn("tracker-performance", portfolio_tracker.render_tracker_html(model))

    def test_interactive_chart_prefers_recorded_sheet_ath_baseline(self):
        history = {"snapshots": [
            {"market_date": "2025-12-31", "accounts": {"tfsa_ws": {"cad": 150000.0}}},
            {"market_date": "2026-01-02", "accounts": {"tfsa_ws": {"cad": 120000.0}}},
            {"market_date": "2026-08-14", "accounts": {"tfsa_ws": {"cad": 125000.0}}},
        ], "ath_reference": {"cad": 155000.0, "source": "Google Sheet · TFSA/WS · ATH row"}}
        model = portfolio_tracker.build_tracker_model(history)
        html = portfolio_tracker.render_tracker_html(model)
        self.assertEqual(model["ath_cad"], 155000.0)
        self.assertFalse(model["ath_is_reconstructed"])
        self.assertIn('data-ath-cad="155000.00"', html)
        self.assertIn('data-ath-source="Google Sheet · TFSA/WS · ATH row"', html)
        self.assertIn("ath=Number(root.dataset.athCad)", html)
        self.assertIn("delta=point.cad-ath", html)
        self.assertIn("showAth(p)", html)
        self.assertIn("showAth(last)", html)
        self.assertIn("%) · ATH", html)
        self.assertIn("draw('YTD')", html)
        self.assertNotIn("%) · '+range", html)

    def test_tracker_labels_reconstructed_ath_when_sheet_reference_is_unavailable(self):
        history = {"snapshots": [
            {"market_date": "2026-01-02", "accounts": {"tfsa_ws": {"cad": 120000.0}}},
            {"market_date": "2026-08-14", "accounts": {"tfsa_ws": {"cad": 125000.0}}},
        ]}
        model = portfolio_tracker.build_tracker_model(history)
        self.assertEqual(model["ath_cad"], 125000.0)
        self.assertTrue(model["ath_is_reconstructed"])
        self.assertIn("Available recorded close history · reconstructed", portfolio_tracker.render_tracker_html(model))

    def test_upsert_persists_user_entered_sheet_ath_reference(self):
        history = portfolio_tracker.upsert_daily_snapshot(
            {"snapshots": []}, {"total_cad": 121000.0, "ath": 152500.0}, {},
            now=datetime(2026, 8, 14, 22, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(history["ath_reference"]["cad"], 152500.0)
        self.assertEqual(history["ath_reference"]["source"], "Google Sheet · TFSA/WS · ATH row")


if __name__ == "__main__":
    unittest.main()
