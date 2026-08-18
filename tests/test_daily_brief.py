import tempfile
import unittest
from pathlib import Path

from daily_brief import render_daily_html, write_daily


class DailyBriefTests(unittest.TestCase):
    def setUp(self):
        self.kwargs = dict(
            portfolio_data={"HG.CN": {"price": 6.84, "change": 0.0, "close_price": 6.84, "close_change": 5.2, "value": 50000}},
            holdings=[{"ticker": "HG.CN", "display": "HG"}],
            tracker_model={"market_date": "2026-08-17", "accounts": {
                "tfsa_ws": {"series": [{"market_date": "2026-01-02", "cad": 80000}, {"market_date": "2026-08-01", "cad": 90000}, {"market_date": "2026-08-17", "cad": 100000}]},
                "kraken": {"series": [{"market_date": "2026-01-02", "usd": 7000}, {"market_date": "2026-08-01", "usd": 8000}, {"market_date": "2026-08-17", "usd": 9000}]},
            }},
            kraken_meta={"position_weights_pct": [("SUI", 38.0), ("ADA", 20.0)]},
            crypto={"SUI": {"change": -2.0}},
            evo_positions=[{"symbol": "PHYS", "value": 700000, "change": 1.0}],
            alpaca={"tier1_positions": [{"symbol": "ABCD", "market_value": 300, "day_change": 3}], "tier2_positions": [], "cash": 200},
            zh_news=[{"title": "Stocks Rally As Yields Fall", "url": "https://example.com/market"}, {"title": "China Tariff Tensions Rise", "url": "https://example.com/geo"}],
            catalysts={"HG.CN": {"title": "HydroGraph announces expansion", "url": "https://example.com/hg"}},
        )

    def test_daily_has_four_accounts_headlines_and_five_percent_mover(self):
        html = render_daily_html(**self.kwargs)
        for label in ("WS TFSA", "Kraken", "RRSP", "Novairecito"):
            self.assertIn(label, html)
        self.assertIn("+5.2%", html)
        self.assertIn("HydroGraph announces expansion", html)
        self.assertIn("Stocks Rally As Yields Fall", html)
        self.assertIn("China Tariff Tensions Rise", html)
        self.assertIn("MTD", html)
        self.assertIn("YTD", html)

    def test_write_daily_creates_route(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio" / "daily" / "index.html"
            write_daily(path, **self.kwargs)
            self.assertTrue(path.exists())
            self.assertIn("The Daily.", path.read_text())


if __name__ == "__main__":
    unittest.main()
