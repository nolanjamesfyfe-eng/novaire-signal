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

    def test_consensus_quote_uses_median_across_exchange_and_derived_sources(self):
        yahoo = {"price": 7747.25, "change": -0.74, "source": "Yahoo Finance"}
        investing = {
            "exchange": {"price": 7770.25, "change": 0.02, "name": "Investing.com Exchange"},
            "derived": {"price": 7748.6, "change": 0.04, "name": "Investing.com Derived"},
        }
        quote = generate.build_futures_consensus(yahoo, investing)
        self.assertEqual(quote["price"], 7770.25)
        self.assertEqual(quote["change"], 0.02)
        self.assertEqual(quote["signal"], "mixed")
        self.assertEqual(quote["source_count"], 3)

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

    def test_commodities_preserve_approved_set_and_add_rbob_gasoline_crack(self):
        commodities = generate.fetch_commodities()
        self.assertEqual(
            set(commodities),
            {"GOLD", "SILVER", "COPPER", "WTI", "BRENT", "URANIUM_SPOT", "RBOB_CRACK"},
        )
        self.assertEqual(commodities["URANIUM_SPOT"]["name"], "Uranium")
        self.assertEqual(commodities["URANIUM_SPOT"]["unit"], "/lb")
        self.assertEqual(commodities["RBOB_CRACK"]["name"], "RBOB Crack")
        self.assertEqual(commodities["RBOB_CRACK"]["unit"], "/bbl")

    def test_rbob_crack_uses_aligned_adjacent_bars_and_42_gallons_per_barrel(self):
        rbob = {"chart": {"result": [{"timestamp": [100, 200, 300], "indicators": {"quote": [{"close": [2.50, 2.60, 2.70]}]}}]}}
        wti = {"chart": {"result": [{"timestamp": [100, 200, 300], "indicators": {"quote": [{"close": [80.0, 82.0, 84.0]}]}}]}}
        quote = generate.parse_rbob_crack(rbob, wti)
        self.assertAlmostEqual(quote["price"], 29.4)
        self.assertAlmostEqual(quote["previous"], 27.2)
        self.assertAlmostEqual(quote["change"], (29.4 - 27.2) / 27.2 * 100)
        self.assertEqual(quote["formula"], "RBOB × 42 − WTI")


if __name__ == "__main__":
    unittest.main()
