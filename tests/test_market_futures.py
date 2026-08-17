from __future__ import annotations

import unittest

import generate


class MarketFuturesTests(unittest.TestCase):
    def test_parse_yahoo_chart_uses_adjacent_valid_bars(self):
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "regularMarketTime": 1786739967,
                            "currency": "USD",
                        },
                        "timestamp": [1786455000, 1786541400, 1786627800, 1786714200],
                        "indicators": {
                            "quote": [
                                {
                                    "close": [23250.0, None, 23400.0, 23517.0],
                                }
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }

        quote = generate.parse_yahoo_chart_quote(payload)

        self.assertEqual(quote["price"], 23517.0)
        self.assertEqual(quote["previous"], 23400.0)
        self.assertAlmostEqual(quote["change"], 0.5)
        self.assertEqual(quote["source"], "Yahoo Finance")
        self.assertEqual(quote["period"], "futures session")
        self.assertEqual(quote["quote_time"], "2026-08-14T20:39:27Z")

    def test_fixed_futures_map_is_sp_nasdaq_and_dow(self):
        self.assertEqual(
            list(generate.MARKET_FUTURES),
            ["ES=F", "NQ=F", "YM=F"],
        )

    def test_cash_index_map_matches_requested_benchmarks(self):
        self.assertEqual(
            list(generate.MARKET_INDICES),
            ["^GSPC", "^IXIC", "^DJI"],
        )
        self.assertEqual(generate.MARKET_INDICES["^IXIC"]["label"], "Nasdaq Composite")

    def test_commodities_preserve_uranium_alongside_investing_screen_set(self):
        commodities = generate.fetch_commodities()
        self.assertEqual(
            set(commodities),
            {"GOLD", "SILVER", "COPPER", "WTI", "BRENT", "NATGAS", "URANIUM_SPOT"},
        )
        self.assertEqual(commodities["URANIUM_SPOT"]["name"], "Uranium")
        self.assertEqual(commodities["URANIUM_SPOT"]["unit"], "/lb")


if __name__ == "__main__":
    unittest.main()
