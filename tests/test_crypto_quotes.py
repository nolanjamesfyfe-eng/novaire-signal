from __future__ import annotations

import time
import unittest
from unittest.mock import patch

import generate


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class CryptoQuoteTests(unittest.TestCase):
    def test_stale_binance_quote_does_not_overwrite_fresh_coingecko_quote(self):
        now_ms = int(time.time() * 1000)
        coingecko_rows = [
            {
                "id": "the-open-network",
                "current_price": 1.33,
                "price_change_percentage_24h": 0.2,
                "market_cap": 3_200_000_000,
                "last_updated": "2026-08-15T07:00:30.000Z",
            }
        ]

        def fake_get(url, **kwargs):
            if "coingecko.com" in url:
                return FakeResponse(coingecko_rows)
            if "GRAMUSDT" in url:
                return FakeResponse(
                    {
                        "lastPrice": "1.60000000",
                        "priceChangePercent": "0.946",
                        "closeTime": now_ms - (39 * 24 * 60 * 60 * 1000),
                    }
                )
            raise RuntimeError("pair unavailable")

        with patch.object(generate.requests, "get", side_effect=fake_get):
            quotes = generate.fetch_crypto()

        self.assertEqual(quotes["TON"]["price"], 1.33)
        self.assertEqual(quotes["TON"]["change"], 0.2)
        self.assertEqual(quotes["TON"]["source"], "CoinGecko")
        self.assertEqual(quotes["TON"]["quote_time"], "2026-08-15T07:00:30.000Z")

    def test_ton_display_uses_active_gram_successor_pair(self):
        now_ms = int(time.time() * 1000)

        def fake_get(url, **kwargs):
            if "coingecko.com" in url:
                return FakeResponse([])
            if "GRAMUSDT" in url:
                return FakeResponse(
                    {
                        "lastPrice": "1.33200000",
                        "priceChangePercent": "0.226",
                        "closeTime": now_ms - 1_000,
                    }
                )
            raise RuntimeError("pair unavailable")

        with patch.object(generate.requests, "get", side_effect=fake_get):
            quotes = generate.fetch_crypto()

        self.assertEqual(generate.CRYPTO_BINANCE_PAIRS["TON"], "GRAMUSDT")
        self.assertEqual(quotes["TON"]["price"], 1.332)
        self.assertEqual(quotes["TON"]["source"], "Binance")


if __name__ == "__main__":
    unittest.main()
