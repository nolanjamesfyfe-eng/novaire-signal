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
        self.assertIn('.market-future{padding:10px 8px}', self.html)
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

    def test_cash_indices_are_tracked_by_api_but_hidden_from_wall_street_card(self):
        for symbol in ("^GSPC", "^IXIC", "^DJI"):
            self.assertNotIn(f'data-market-price="{symbol}"', self.html)
            self.assertNotIn(f'data-market-change="{symbol}"', self.html)
        self.assertNotIn("<i>Cash</i>", self.html)

    def test_market_quotes_and_percentages_use_shared_sizes(self):
        self.assertIn("--market-quote-size:.95rem;--market-change-size:.68rem;--market-number-weight:500", self.html)
        for selector in (".market-future b", ".commodity-price", ".crypto-price"):
            self.assertIn(f"{selector}", self.html)
        self.assertIn("font-size:var(--market-quote-size)", self.html)
        self.assertIn("font-size:var(--market-change-size)", self.html)
        for label in ("S&amp;P 500", "NASDAQ 100", "DOW JONES"):
            self.assertIn(label, self.html)
        self.assertNotIn("CONSENSUS", self.html)
        self.assertNotIn("q.sourceCount", self.html)
        self.assertIn("CME/CBOT front-month future", self.html)
        self.assertIn("grid-template-columns:repeat(4,minmax(0,1fr))", self.html)
        self.assertIn("grid-template-areas:\"primary futures futures futures\" \"calendar calendar calendar calendar\"", self.html)
        self.assertIn(".market-primary{grid-area:primary;display:flex;flex-direction:column", self.html)
        self.assertIn(".market-future{display:flex;flex-direction:column", self.html)
        self.assertIn(".commodity-price{display:flex;align-items:baseline;justify-content:center;gap:3px;white-space:nowrap;font-family:var(--serif);font-size:var(--market-quote-size);font-weight:var(--market-number-weight);color:var(--text)", self.html)
        self.assertIn(".crypto-price{font-family:var(--serif);font-size:var(--market-quote-size);font-weight:var(--market-number-weight);color:var(--text)", self.html)
        self.assertIn(".fx-chip .fx-rate{display:block;font-family:'Courier New',monospace;font-size:.78rem;font-weight:600;color:var(--text)", self.html)
        self.assertNotRegex(self.html, r'class="crypto-price"[^>]*style="color:')
        self.assertIn("background:var(--bg);padding:9px;border:1px solid var(--border);border-radius:var(--r);text-align:center", self.html)
        self.assertIn(".market-calendar{grid-area:calendar", self.html)
        self.assertIn("text-align:center", self.html)

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
        self.assertIn(">🎯 Daily Keystone</div>", self.html)
        self.assertIn(">⚔️ Daily Actions</div>", self.html)
        self.assertIn("split(/[,;\\n]+/)", self.html)
        self.assertIn("Run one 25-minute Pomodoro", self.html)
        self.assertIn("Do your Anki review at the start of the day", self.html)
        self.assertIn("Do you have the high-quality audio ready?", self.html)
        self.assertIn("Start one load of laundry", self.html)
        self.assertIn("novaire-keystone-streak", self.html)
        self.assertIn("calculateKeystoneStreak", self.html)
        self.assertIn("every(item => feedback[item.id]?.status === 'completed')", self.html)
        self.assertIn("novaire-keystone-learning", self.html)
        self.assertIn("status:'ricies'", self.html)
        self.assertIn("Avoid this suggestion next time", self.html)
        self.assertIn('id="daily-actions-card" open', self.html)
        self.assertIn("rememberAccordionPreferences", self.html)
        self.assertNotIn("manageDailyActionsDisclosure", self.html)
        self.assertNotIn("entry.boundingClientRect.bottom < 0", self.html)
        self.assertIn("event.key === 'Enter'", self.html)
        self.assertIn(">Ricies</button>", self.html)
        self.assertIn("items.map((item,index)", self.html)

    def test_catalysts_stay_on_main_signal_but_not_portfolio(self):
        heading = "🔍 Catalysts — Top 5 Holdings"
        self.assertIn(heading, self.html)
        self.assertNotIn(heading, self.portfolio_html)

    def test_crypto_position_weighting_uses_live_kraken_sheet_mix(self):
        self.assertIn('id="crypto-position-weighting"', self.portfolio_html)
        self.assertIn("Crypto Position Weighting", self.portfolio_html)
        self.assertIn("What's Kraken 2025 · % of Fund · live source of truth", self.portfolio_html)
        self.assertIn('data-allocation-sector="SUI"', self.portfolio_html)
        self.assertRegex(self.portfolio_html, r"SUI</text><text[^>]+>\d+\.\d% WEIGHT")

    def test_portfolio_summary_uses_honest_return_labels(self):
        self.assertIn("Unrealized ROI", self.portfolio_html)
        self.assertIn("Unrealized P&amp;L CAD", self.portfolio_html)
        self.assertIn("Off ATH", self.portfolio_html)
        self.assertIn("ATH Gap CAD", self.portfolio_html)
        self.assertIn("YTD Return", self.portfolio_html)
        self.assertIn("YTD needs Jan 1 NAV plus dated deposits and withdrawals", self.portfolio_html)
        self.assertNotIn("ATH (w/ w/d)", self.portfolio_html)
        self.assertNotIn("ROI Abs.", self.portfolio_html)
        self.assertNotIn(">+109.0%</div>", self.portfolio_html)

    def test_portfolio_tickers_open_nine_month_weekly_candles(self):
        self.assertIn('class="ticker chart-ticker"', self.portfolio_html)
        self.assertIn('data-chart-symbol="HG.CN"', self.portfolio_html)
        self.assertIn('id="holding-chart-dialog"', self.portfolio_html)
        self.assertIn("/api/stock-chart?symbol=", self.portfolio_html)
        self.assertIn("9 months · 39 weekly candles + volume · Current week through prior close", self.portfolio_html)
        self.assertIn("FIRST", self.portfolio_html)
        self.assertIn("LAST", self.portfolio_html)
        self.assertIn("last close", self.portfolio_html)
        self.assertIn("ACTIVE WEEK", self.portfolio_html)
        self.assertIn("C ${fmt(last.close)}", self.portfolio_html)
        self.assertIn("VOLUME", self.portfolio_html)
        self.assertIn("HIGH", self.portfolio_html)
        self.assertIn("LOW", self.portfolio_html)
        self.assertIn("prior close", self.portfolio_html)
        self.assertNotIn("Previous close", self.portfolio_html)
        self.assertIn("role=\"img\"", self.portfolio_html)

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
        self.assertIn('class="card signal-accordion trading-accordion" id="darvas-card"', self.html)

    def test_alpaca_is_canonical_live_holdings_source_with_weights(self):
        self.assertIn("🦙 Alpaca · Novairecito", self.html)
        self.assertNotIn("🦙 Alpaca · Livermore Darvas", self.html)
        self.assertIn("Live Alpaca holdings", self.html)
        self.assertIn('data-alpaca-positions', self.html)
        self.assertIn('data-alpaca-symbol="URNJ"', self.html)
        self.assertIn('class="alpaca-weight"', self.html)
        self.assertIn("data.positions", self.html)
        self.assertIn("portfolioWeight", self.html)
        # Polymarket may be omitted when its live API is rate-limited; if rendered,
        # it must remain a compact accordion.
        if 'id="polymarket-card"' in self.html:
            self.assertIn('class="card signal-accordion trading-accordion" id="polymarket-card"', self.html)
        self.assertIn("Updated on Aug 10", self.html)
        self.assertIn("Updated on Aug 17", self.html)
        self.assertNotIn("Updated 2026-", self.html)
        self.assertIn("nv_weekly_ideas_seen", self.html)
        self.assertIn('data-fingerprint=', self.html)
        self.assertIn("function rememberAccordionPreferences()", self.html)
        self.assertIn("document.querySelectorAll('details.signal-accordion[id]')", self.html)
        self.assertIn("const key = 'nv_accordion_state_' + card.id", self.html)
        self.assertIn("card.open = saved === 'open'", self.html)
        self.assertIn("localStorage.setItem(key, card.open ? 'open' : 'closed')", self.html)
        self.assertNotIn("const key = 'nv_catalysts_seen'", self.html)
        self.assertNotIn("if (hasBeenVisible && card.open", self.html)
        self.assertIn("const meditationCardKey = 'nv_meditation_card_viewed'", self.html)
        self.assertIn("cardDone || (meditationDone && quoteDone)", self.html)
        self.assertIn("function restoreMeditationShell()", self.html)
        self.assertIn("restoreMeditationShell();", self.html)
        self.assertNotIn("if (consumed) meditationCard.removeAttribute('open')", self.html)
        self.assertIn("if (!meditationCard.open) localStorage.setItem(meditationCardKey, meditationCard.dataset.edition)", self.html)
        self.assertIn('details.addEventListener(\'toggle\'', self.html)
        if 'id="polymarket-card"' in self.html:
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
        self.assertIn(".daily-signal-card:not([open]){height:62px;min-height:62px}", self.html)
        self.assertIn(".card.daily-signal-card{padding:0;overflow:hidden}", self.html)
        self.assertIn(".daily-signal-card:not([open])>summary{height:62px;min-height:62px}", self.html)
        self.assertIn(".daily-signal-card.is-viewed{height:62px;min-height:62px}", self.html)
        self.assertIn(".daily-signal-card.is-viewed>.signal-accordion-body{display:none}", self.html)
        self.assertIn("card.classList.add('is-viewed')", self.html)
        self.assertIn("card.classList.toggle('is-viewed', !card.open)", self.html)

    def test_commodities_are_six_compact_tiles_with_diesel(self):
        self.assertIn(".commodities-grid{display:grid;grid-template-columns:repeat(6,1fr)", self.html)
        self.assertIn(".commodity-item{background:var(--bg);padding:9px", self.html)
        self.assertIn(".commodity-name{font-size:.58rem", self.html)
        self.assertIn(".market-future span{font-size:.58rem", self.html)
        self.assertIn(".crypto-symbol{font-size:.58rem", self.html)
        self.assertIn(".commodity-price{display:flex;align-items:baseline;justify-content:center", self.html)
        self.assertIn('<span class="commodity-unit">/oz</span>', self.html)
        self.assertNotIn('<div class="commodity-unit">', self.html)
        self.assertNotIn('data-commodity="NATGAS"', self.html)
        self.assertNotIn('data-commodity="BRENT"', self.html)
        self.assertNotIn('data-commodity="RBOB_CRACK"', self.html)
        for symbol in ("GOLD", "SILVER", "COPPER", "WTI", "URANIUM_SPOT", "DIESEL"):
            self.assertIn(f'data-commodity="{symbol}"', self.html)
        self.assertIn('<div class="commodity-name c-oil">Crude Oil</div>', self.html)
        self.assertNotIn("Crude Oil WTI", self.html)

    def test_trading_summary_typography_and_signal_colors_match_fed(self):
        self.assertIn(".accordion-score,.accordion-score b,.fed-summary-rate,.fed-summary-sentiment{font-size:.68rem", self.html)
        self.assertNotIn("#4ade80", self.html)
        self.assertNotIn("#f87171", self.html)
        self.assertIn("el.style.color=roi>=0?'var(--green)':'var(--red)'", self.html)

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

    def test_net_worth_chart_stays_below_metrics_and_period_tiles_wrap(self):
        html = self.portfolio_html
        self.assertIn(".tracker-hero-metric{position:relative", html)
        self.assertNotIn(".tracker-hero-metric{position:absolute", html)
        self.assertIn(".tracker-performance-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(78px,1fr))", html)
        self.assertIn(".tracker-performance-grid{grid-template-columns:repeat(2,minmax(0,1fr))", html)
        self.assertIn(".tracker-performance-grid>div:last-child:nth-child(odd){grid-column:1/-1}", html)
        self.assertNotIn("minmax(68px,1fr)", html)
        self.assertNotIn(".tracker-hero-svg{display:block;width:100%;height:260px;overflow:visible", html)

    def test_economies_open_once_then_remember_viewed_edition(self):
        # The biweekly card is intentionally absent outside its scheduled Monday;
        # persistence machinery remains in every build.
        if 'id="economies-card"' in self.html:
            self.assertIn('data-edition="2026-W34"', self.html)
        self.assertIn("nv_economies_seen", self.html)
        self.assertIn("IntersectionObserver", self.html)


if __name__ == "__main__":
    unittest.main()