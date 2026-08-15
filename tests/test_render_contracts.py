from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RenderContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_market_strip_is_between_weather_and_fx(self):
        weather = self.html.index("🌤 Weather")
        market = self.html.index("🗽 Wall Street")
        fx = self.html.index("💱 FX Rates")
        self.assertLess(weather, market)
        self.assertLess(market, fx)

    def test_fed_signal_is_immediately_below_top_five_catalysts(self):
        catalysts = self.html.index("🔍 Catalysts — Top 5 Holdings")
        fed = self.html.index("🏛️ Fed Signal")
        trading_books = self.html.index("<!-- TRADING BOOKS")
        self.assertLess(catalysts, fed)
        self.assertLess(fed, trading_books)

    def test_requested_cash_indices_are_present(self):
        for symbol in ("^GSPC", "^IXIC", "^DJI"):
            self.assertIn(f'data-market-price="{symbol}"', self.html)
            self.assertIn(f'data-market-change="{symbol}"', self.html)

    def test_ton_poll_uses_active_gram_pair(self):
        self.assertIn('"TON":"GRAMUSDT"', self.html)
        self.assertNotIn('"TON":"TONUSDT"', self.html)

    def test_text_is_scaled_without_scaling_logo(self):
        self.assertIn("html{scroll-behavior:smooth;font-size:110%}", self.html)
        self.assertIn("font-size:18.15px", self.html)
        self.assertIn(".footer-logo{font-family:var(--serif);font-size:1.6363636rem", self.html)

    def test_approved_bolt_and_retired_vote_contract(self):
        self.assertIn('<span aria-hidden="true">&#x26A1;&#xFE0E;</span>', self.html)
        for forbidden in (
            "Daily Updog Vote",
            "Daily product senate",
            'id="updog-card"',
            "renderUpdogVotes",
            "UPDOG_SUGGESTIONS",
            "UPDOG_ACTION_STEPS",
            "handleUpdogVote",
        ):
            self.assertNotIn(forbidden, self.html)
        self.assertIn("data.isSet", self.html)
        self.assertIn("moves.every", self.html)


if __name__ == "__main__":
    unittest.main()