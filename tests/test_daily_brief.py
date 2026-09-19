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
            alpaca={"tier1_positions": [{"symbol": "ABCD", "market_value": 300, "day_change": 0, "close_change": 3, "day_high": 12, "day_low": 10, "completed_market_date": "2026-08-17", "qty": 25, "portfolio_weight": 60}], "tier2_positions": [], "cash": 200, "equity": 500, "last_equity": 490},
            gs_meta={"total_cad": 100000},
            fx={"usdcad": 1.365, "audusd": .63},
            zh_news=[{"title": "Stocks Rally As Yields Fall", "url": "https://example.com/market"}, {"title": "China Tariff Tensions Rise", "url": "https://example.com/geo"}],
            catalysts={"HG.CN": {"title": "HydroGraph announces expansion", "url": "https://example.com/hg"}},
        )

    def test_daily_has_source_correct_accounts_and_impact_snapshot(self):
        html = render_daily_html(**self.kwargs)
        for label in ("WS TFSA", "RRSP", "Novairecito"):
            self.assertIn(label, html)
        self.assertNotIn("Kraken", html)
        for label in ("LARGEST POSITION", "DAY HIGH", "DAY LOW", "PORTFOLIO DAILY EFFECT", "POSITION SESSION RANGE", "NET WORTH EFFECT"):
            self.assertIn(label, html)
        self.assertNotIn("INTRADAY CASH SWING", html)
        self.assertIn("Google Sheet · RRSP", html)
        self.assertIn("30.0% of portfolio", html)
        self.assertNotIn("PHYS", html)
        self.assertIn("C$113,182 tracked net worth", html)
        self.assertIn("HydroGraph announces expansion", html)

    def test_daily_effect_is_whole_account_close_delta_not_largest_holding(self):
        html = render_daily_html(**self.kwargs)
        # TFSA history moved C$10,000; the largest holding's isolated move is only ~C$2,471.
        self.assertIn("+C$10,000", html)
        self.assertNotIn("+C$2,471", html)
        # Alpaca exposes broker prior equity, so its whole-book delta is US$10.
        self.assertIn("+C$14", html)
        self.assertIn("+3.0%", html)
        self.assertIn("US$12.00", html)
        self.assertIn("US$10.00", html)
        self.assertIn("Largest-position high to low; not whole-account swing", html)

    def test_position_range_is_not_mislabeled_as_account_intraday_swing(self):
        html = render_daily_html(**self.kwargs)
        self.assertEqual(html.count("Largest-position high to low; not whole-account swing"), 3)
        self.assertNotIn("INTRADAY SWING", html)

    def test_time_aligned_account_series_is_not_summed_into_position_range(self):
        kwargs = dict(self.kwargs)
        kwargs["account_intraday"] = {
            "tfsa_ws": [{"timestamp": "14:30", "cad": 99000}, {"timestamp": "14:35", "cad": 101250}, {"timestamp": "14:40", "cad": 100000}],
        }
        html = render_daily_html(**kwargs)
        self.assertNotIn("+C$2,250", html)
        self.assertIn("+C$8,500", html)

    def test_accounts_are_compact_collapsed_disclosures(self):
        html = render_daily_html(**self.kwargs)
        self.assertEqual(html.count('<details class="account"'), 3)
        self.assertEqual(html.count("<summary>"), 3)
        self.assertNotIn('<details class="account" open', html)
        self.assertIn("grid-template-columns:minmax(0,1fr) minmax(0,auto) 14px", html)
        self.assertNotIn("position:absolute", html)
        self.assertIn("overflow-wrap:anywhere", html)
        self.assertIn("min-height:32px", html)
        self.assertIn("summary{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,auto) 14px;align-items:center;gap:10px;min-height:32px;padding:7px 12px", html)
        self.assertIn("padding:7px 8px", html)

    def test_compact_daily_header_reuses_approved_brand_navigation(self):
        html = render_daily_html(**self.kwargs)
        self.assertIn('<header class="daily-header"><div class="signal-brand-row"', html)
        self.assertIn('family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400;1,500', html)
        self.assertIn('<h1 class="daily-title">The Daily.</h1>', html)
        self.assertIn("margin:49px 0 18px", html)
        self.assertIn("margin-top:56.765625px", html)
        self.assertIn('href="/" class="signal-wordmark"', html)
        self.assertIn('href="/flaneur" class="signal-map"', html)
        self.assertIn('href="/portfolio/" class="signal-bolt"', html)
        self.assertIn('viewBox=".85 .85 22.3 22.3"', html)
        self.assertIn('viewBox="45 38 200 264"', html)
        self.assertIn("#b59662", html)

    def test_daily_has_only_accounts_and_qualifying_moves(self):
        html = render_daily_html(**self.kwargs)
        self.assertNotIn("Market mover · ZeroHedge", html)
        self.assertNotIn("https://example.com/market", html)
        self.assertNotIn("Geopolitical pressure", html)
        self.assertNotIn('href="https://example.com/geo"', html)
        self.assertNotIn('class="story"', html)
        self.assertIn('<section class="movers"><div class="section-label">Portfolio moves · ±5%</div>', html)
        self.assertIn('class="mover" href="https://example.com/hg"', html)
        self.assertIn("grid-template-columns:repeat(2,minmax(0,1fr))", html)
        self.assertIn(".section-label{grid-column:1/-1", html)
        self.assertIn("@media(max-width:760px){.accounts,.movers{grid-template-columns:1fr}", html)

    def test_sub_five_percent_move_stays_excluded(self):
        kwargs = dict(self.kwargs)
        kwargs["portfolio_data"] = {
            "HG.CN": {**self.kwargs["portfolio_data"]["HG.CN"], "close_change": 4.99}
        }
        html = render_daily_html(**kwargs)
        self.assertNotIn("HydroGraph announces expansion", html)
        self.assertIn("No portfolio position moved ±5% at the latest close.", html)

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
