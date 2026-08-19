import tempfile
import unittest
from pathlib import Path

from daily_brief import render_daily_html, write_daily
from portfolio_tracker import parse_rrsp_rows


class DailyBriefTests(unittest.TestCase):
    def setUp(self):
        self.kwargs = dict(
            portfolio_data={"HG.CN": {"price": 6.84, "close_price": 6.84, "previous_close": 6.50, "close_change": 5.2, "day_high": 7.10, "day_low": 6.25, "value": 50000}},
            holdings=[{"ticker": "HG.CN", "display": "HG", "shares": 10000, "currency": "CAD"}],
            tracker_model={"market_date": "2026-08-17", "accounts": {
                "tfsa_ws": {"current_cad": 100000, "series": [{"market_date": "2026-01-02", "cad": 80000}, {"market_date": "2026-08-01", "cad": 90000}, {"market_date": "2026-08-17", "cad": 100000}]},
                "kraken": {"current_cad": 12300, "current_usd": 9000, "series": [{"market_date": "2026-01-02", "usd": 7000}, {"market_date": "2026-08-01", "usd": 8000}, {"market_date": "2026-08-17", "usd": 9000}]},
            }},
            kraken_meta={"total_usd": 9000, "total_cad": 12300, "position_weights_pct": [("SUI", 38.0), ("ADA", 20.0)]},
            crypto={"SUI": {"price": 3.0, "change": -2.0, "day_high": 3.2, "day_low": 2.8}},
            rrsp_meta={"total_cad": 12500, "positions": [{"symbol": "HG", "currency": "CAD", "shares": 600, "value_cad": 3750, "weight_pct": 30.0}]},
            rrsp_quotes={"HG": {"close_price": 6.25, "close_change": -8.6, "day_high": 6.90, "day_low": 6.10}},
            alpaca={"tier1_positions": [{"symbol": "ABCD", "market_value": 300, "day_change": 3, "portfolio_weight": 60}], "tier2_positions": [], "cash": 200, "equity": 500},
            gs_meta={"total_cad": 100000},
            fx={"usdcad": 1.365, "audusd": .63},
            zh_news=[{"title": "Stocks Rally As Yields Fall", "url": "https://example.com/market"}, {"title": "China Tariff Tensions Rise", "url": "https://example.com/geo"}],
            catalysts={"HG.CN": {"title": "HydroGraph announces expansion", "url": "https://example.com/hg"}},
        )

    def test_daily_has_source_correct_accounts_and_impact_snapshot(self):
        html = render_daily_html(**self.kwargs)
        for label in ("WS TFSA", "Kraken", "RRSP", "Novairecito"):
            self.assertIn(label, html)
        for label in ("DAY HIGH", "DAY LOW", "DAILY IMPACT", "NET WORTH IMPACT", "HIGH–LOW SWING"):
            self.assertIn(label, html)
        self.assertIn("Google Sheet · RRSP", html)
        self.assertIn("Largest · 30.0% of portfolio", html)
        self.assertNotIn("PHYS", html)
        self.assertIn("C$125,468 tracked net worth", html)
        self.assertIn("HydroGraph announces expansion", html)

    def test_accounts_are_compact_collapsed_disclosures(self):
        html = render_daily_html(**self.kwargs)
        self.assertEqual(html.count('<details class="account"'), 4)
        self.assertEqual(html.count("<summary>"), 4)
        self.assertNotIn('<details class="account" open', html)
        self.assertIn("grid-template-columns:minmax(0,1fr) auto 14px", html)

    def test_rrsp_parser_uses_dedicated_sheet_values(self):
        rows = [
            ["", "CAD", "HydroGraph", "CNSX:HG", "", "$6.25", "", "", "600"],
            ["", "CAD", "Global Atomic", "TSE:GLO", "", "$0.54", "", "", "5000"],
            ["", "USD", "Bannerman", "BNNLF", "", "$2.54", "", "", "300"],
        ]
        parsed = parse_rrsp_rows(rows, usdcad=1.365)
        self.assertEqual(parsed["sheet_gid"], "164741412")
        self.assertEqual(parsed["positions"][0]["symbol"], "HG")
        self.assertAlmostEqual(parsed["positions"][0]["value_cad"], 3750)
        self.assertNotEqual(parsed["positions"][0]["symbol"], "PHYS")

    def test_write_daily_creates_route(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio" / "daily" / "index.html"
            write_daily(path, **self.kwargs)
            self.assertTrue(path.exists())
            self.assertIn("The Daily.", path.read_text())


if __name__ == "__main__":
    unittest.main()
