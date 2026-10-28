"""Every market tile (Wall Street, commodities, crypto, FX) opens its live chart."""
from pathlib import Path
import re
import unittest

from bs4 import BeautifulSoup

import generate

ROOT = Path(__file__).resolve().parents[1]


class MarketChartLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.soup = BeautifulSoup((ROOT / "index.html").read_text(encoding="utf-8"), "html.parser")

    def assert_linked(self, selector, expected):
        tiles = self.soup.select(selector)
        self.assertEqual(len(tiles), expected, selector)
        for tile in tiles:
            self.assertEqual(tile.name, "a", selector)
            self.assertRegex(tile["href"], r"^https://www\.investing\.com/")
            self.assertEqual(tile["target"], "_blank")
            self.assertIn("noopener", tile["rel"])
            self.assertIn("market-link", tile["class"])

    def test_every_market_tile_clicks_through(self):
        self.assert_linked(".market-futures .market-future", len(generate.MARKET_FUTURES) + len(generate.MARKET_SIGNALS))
        self.assert_linked(".commodities-grid .commodity-item", 6)
        self.assert_linked(".crypto-grid .crypto-item", 8)
        self.assert_linked(".fx-row .fx-chip", 8)

    def test_link_maps_cover_every_rendered_symbol(self):
        for symbol in list(generate.MARKET_FUTURES) + list(generate.MARKET_SIGNALS):
            self.assertIn(symbol, generate.MARKET_CHART_LINKS)
        self.assertEqual(set(generate.CRYPTO_CHART_LINKS), set(generate.CRYPTO_BINANCE_PAIRS))

    def test_wall_street_header_matches_section_titles_with_clock_right(self):
        title = self.soup.select_one(".market-card > .card-title.market-title")
        self.assertIsNotNone(title)
        self.assertIn("Wall Street", title.select_one(".market-title-label").get_text())
        clock = title.select_one(".wall-time.live-clock")
        self.assertEqual(clock["data-tz"], "America/New_York")
        self.assertIsNone(self.soup.select_one(".market-primary"))
        labels = [tile.select_one("span").get_text(" ", strip=True) for tile in self.soup.select(".market-future")]
        self.assertEqual(labels, ["S&P 500", "NASDAQ 100", "DOW JONES"])

    def test_tencent_parser_reads_csi300(self):
        payload = 'v_sh000300="1~x~000300~4083.87~4049.55~' + "~".join(["0"] * 25) + '~20261028161412~34.32~0.85~"'
        quote = generate.parse_tencent_index_quote(payload)
        self.assertEqual(quote["price"], 4083.87)
        self.assertEqual(quote["change"], 0.85)
        self.assertEqual(quote["quote_time"], "2026-10-28T08:14:12Z")
        self.assertIsNone(generate.parse_tencent_index_quote('v_sh000300="";'))


if __name__ == "__main__":
    unittest.main()
