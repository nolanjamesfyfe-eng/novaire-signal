from pathlib import Path
from datetime import datetime
import unittest

import generate


ROOT = Path(__file__).resolve().parents[1]


class RenderContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.portfolio_html = (ROOT / "portfolio" / "index.html").read_text(encoding="utf-8")

    def test_market_strip_is_between_weather_and_fx(self):
        weather = self.html.index("🌤 Weather")
        market = self.html.index("🗽 Wall Street")
        fx = self.html.index("💱 FX Rates")
        self.assertLess(weather, market)
        self.assertLess(market, fx)

    def test_mobile_market_and_fx_spacing_contract(self):
        self.assertIn('.market-clock{gap:14px;padding-top:16px;padding-bottom:16px}', self.html)
        self.assertIn('.market-futures{grid-template-columns:1fr;gap:10px}', self.html)
        self.assertIn('column-gap:12px;border-left:none;border-top:1px solid var(--border);padding:10px 0 2px', self.html)
        self.assertIn('.fx-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:8px}', self.html)
        self.assertIn('.fx-chip{padding:9px 4px}', self.html)

    def test_fed_signal_is_immediately_below_top_five_catalysts(self):
        catalysts = self.html.index("🔍 Catalysts — Top 5 Holdings")
        fed = self.html.index("🏛️ Fed Signal")
        trading_books = self.html.index("<!-- TRADING BOOKS")
        self.assertLess(catalysts, fed)
        self.assertLess(fed, trading_books)

    def test_fed_signal_collapses_to_rate_and_latest_sentiment(self):
        self.assertIn('id="fed-signal-card"', self.html)
        self.assertIn('class="fed-summary-rate"', self.html)
        self.assertIn('class="fed-summary-sentiment"', self.html)
        self.assertIn('Hold 55%', self.html)

    def test_requested_cash_indices_are_present(self):
        for symbol in ("^GSPC", "^IXIC", "^DJI"):
            self.assertIn(f'data-market-price="{symbol}"', self.html)
            self.assertIn(f'data-market-change="{symbol}"', self.html)

    def test_wall_street_daily_change_percentages_are_emphasized(self):
        self.assertIn(".market-future em{font-size:.7332rem", self.html)
        self.assertIn(".market-future small u{font-size:.6396rem", self.html)

    def test_ton_poll_uses_active_gram_pair(self):
        self.assertIn('"TON":"GRAMUSDT"', self.html)
        self.assertNotIn('"TON":"TONUSDT"', self.html)

    def test_text_is_scaled_without_scaling_logo(self):
        self.assertIn("html{scroll-behavior:smooth;font-size:110%}", self.html)
        self.assertIn("font-size:18.15px", self.html)
        self.assertIn(".footer-logo{font-family:var(--serif);font-size:1.6363636rem", self.html)

    def test_signal_bolt_is_locked_to_antique_gold_svg(self):
        emoji = '<span aria-hidden="true">&#x26A1;&#xFE0F;</span>'
        text_glyph = '<span aria-hidden="true">&#x26A1;&#xFE0E;</span>'
        bolt_path = "M219 44Q217 43 215 44L51 180Q49 183 51 185"
        old_font_awesome_path = "M32.938 15.651C32.792 15.26 32.418 15 32 15H19.925"
        self.assertEqual(self.html.count('class="signal-bolt-icon"'), 2)
        self.assertEqual(self.html.count(bolt_path), 2)
        self.assertNotIn(old_font_awesome_path, self.html)
        self.assertNotIn(emoji, self.html)
        self.assertNotIn(f'class="signal-bolt">{text_glyph}', self.html)
        self.assertIn(".signal-bolt{display:inline-flex", self.html)
        self.assertIn("color:#b59662", self.html)
        self.assertIn(".signal-bolt-icon{width:.82em;height:1.05em;display:block;fill:currentColor}", self.html)
        self.assertNotIn(".signal-bolt-icon{width:.82em;height:1.05em;display:block;fill:currentColor;filter:", self.html)
        self.assertNotIn("signal-bolt-antique-gold", self.html)
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
        self.assertIn("novaire-keystone-action-index-", self.html)
        self.assertIn("novaire-keystone-streak", self.html)
        self.assertIn("calculateKeystoneStreak", self.html)
        self.assertIn("day complete':' days complete", self.html)
        self.assertIn("Next action generated", self.html)
        self.assertNotIn("state==='incomplete'?\"Didn't complete\":'Completed'", self.html)
        self.assertIn(">Ricies</button>", self.html)
        self.assertNotIn("moves.map((move,index)", self.html)

    def test_catalysts_stay_on_main_signal_but_not_portfolio(self):
        heading = "🔍 Catalysts — Top 5 Holdings"
        self.assertIn(heading, self.html)
        self.assertNotIn(heading, self.portfolio_html)

    def test_latest_novaire_is_compact_metric_accordion(self):
        self.assertEqual(self.html.count('class="latest-novaire-item"'), 4)
        for label in (
            "INSTAGRAM · LATEST POST",
            "YOUTUBE · LATEST CLIP",
            "YOUTUBE · FULL EPISODE",
            "READ · NOVAIRE INK",
        ):
            self.assertIn(label, self.html)
        self.assertIn("views</span>", self.html)
        self.assertIn("likes</span>", self.html)
        self.assertIn("Top engagement", self.html)
        self.assertIn("https://www.instagram.com/j.novaire/", self.html)
        self.assertNotIn('class="latest-novaire-grid"', self.html)

    def test_weekly_sections_open_only_monday_and_tuesday(self):
        self.assertTrue(generate.open_early_week(datetime(2026, 8, 17)))
        self.assertTrue(generate.open_early_week(datetime(2026, 8, 18)))
        self.assertFalse(generate.open_early_week(datetime(2026, 8, 19)))
        self.assertFalse(generate.open_early_week(datetime(2026, 8, 23)))

    def test_clutter_cards_are_accordions_with_compact_summaries(self):
        self.assertIn('class="card signal-accordion" id="weekly-asymmetric-ideas" data-edition="2026-08-10" open', self.html)
        self.assertIn('class="card signal-accordion" id="catalysts-card" data-edition="2026-W34"', self.html)
        self.assertIn('class="card signal-accordion trading-accordion" id="polymarket-card"', self.html)
        self.assertIn('class="card signal-accordion trading-accordion" id="darvas-card"', self.html)
        self.assertIn("Updated on Aug 17", self.html)
        self.assertIn("nv_weekly_ideas_seen", self.html)
        self.assertIn('data-fingerprint=', self.html)
        self.assertIn("const key = 'nv_catalysts_seen'", self.html)
        self.assertIn("if (localStorage.getItem(key) === fingerprint) card.removeAttribute('open')", self.html)
        self.assertIn("if (!card.open) localStorage.setItem(key, fingerprint)", self.html)
        self.assertIn("const meditationCardKey = 'nv_meditation_card_viewed'", self.html)
        self.assertIn("cardDone || (meditationDone && quoteDone)", self.html)
        self.assertIn("if (!meditationCard.open) localStorage.setItem(meditationCardKey, meditationCard.dataset.edition)", self.html)
        self.assertIn('details.addEventListener(\'toggle\'', self.html)
        self.assertIn('44W / 34L', self.html)
        self.assertIn('Inception ROI', self.html)

    def test_latest_instagram_uses_verified_post_cache(self):
        item = generate.load_latest_instagram()
        self.assertEqual(item["url"], "https://www.instagram.com/j.novaire/reel/DbfU2zHiXyU/")
        self.assertIn("Sexuality Maxxing", item["title"])
        self.assertEqual(item["published_at"], "2026-08-01")

    def test_weather_and_world_tour_collapse_to_viewed_for_same_day(self):
        for card_id, score_id, storage_key in (
            ("weather-card", "weather-viewed", "nv_weather_viewed"),
            ("world-tour-card", "world-tour-viewed", "nv_world_tour_viewed"),
            ("quotes-daily", "quotes-viewed", "nv_quotes_viewed"),
        ):
            self.assertIn(f'id="{card_id}"', self.html)
            self.assertIn(f'id="{score_id}"', self.html)
            self.assertIn(storage_key, self.html)
        self.assertIn("rememberDailySignalCard", self.html)
        self.assertIn("score.textContent = 'Viewed'", self.html)

    def test_daily_meditation_reopens_each_new_day_and_remembers_same_day_collapse(self):
        self.assertIn('id="meditation-daily" class="meditation" open', self.html)
        self.assertNotIn('A short Stoic reset for today', self.html)
        self.assertNotIn('carry one sentence into the day', self.html)
        self.assertIn('class="meditation-collapse"', self.html)
        self.assertIn("nv_meditation_collapsed_date", self.html)
        self.assertIn("localDateKey", self.html)
        self.assertIn("meditation.open = collapsedDate !== today", self.html)
        self.assertIn('id="meditation-viewed"', self.html)
        self.assertIn("meditationViewed.textContent = 'Viewed'", self.html)

    def test_thailand_news_collapses_to_viewed_for_same_daily_edition(self):
        self.assertIn('id="thailand-news-card"', self.html)
        self.assertIn('id="thailand-news-viewed"', self.html)
        self.assertIn("nv_thailand_news_viewed", self.html)
        self.assertIn("thailandScore.textContent = 'Viewed'", self.html)

    def test_economies_open_once_then_remember_viewed_edition(self):
        self.assertIn('id="economies-card"', self.html)
        self.assertIn('data-edition="2026-W34"', self.html)
        self.assertIn("nv_economies_seen", self.html)
        self.assertIn("IntersectionObserver", self.html)


if __name__ == "__main__":
    unittest.main()