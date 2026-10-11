from __future__ import annotations

import os
import socketserver
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler
from unittest.mock import Mock, patch

import generate


class MarketFuturesTests(unittest.TestCase):
    def setUp(self):
        generate._FIRECRAWL_BLOCKED_HOSTS.clear()

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
        quote = generate.build_exchange_futures_quote(yahoo, investing)
        self.assertEqual(quote["price"], 7747.25)
        self.assertEqual(quote["change"], -0.74)
        self.assertEqual(quote["source"], "Yahoo Finance · CME/CBOT front month")
        self.assertFalse(quote["is_fallback"])

        fallback = generate.build_exchange_futures_quote({"price": None, "change": None}, investing)
        self.assertEqual(fallback["price"], 7770.25)
        self.assertEqual(fallback["change"], 0.02)
        self.assertTrue(fallback["is_fallback"])

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

    def test_yahoo_commodity_fallback_preserves_all_four_core_quotes(self):
        quotes = generate.fetch_yahoo_commodity_fallback()
        self.assertEqual(set(quotes), {"GOLD", "SILVER", "COPPER", "WTI"})
        for symbol, quote in quotes.items():
            self.assertGreater(quote["price"], 0, symbol)
            self.assertEqual(quote["source"], "Yahoo Finance fallback")

    def test_commodities_use_six_tile_set_with_diesel(self):
        commodities = generate.fetch_commodities()
        self.assertEqual(
            set(commodities),
            {"GOLD", "SILVER", "COPPER", "WTI", "URANIUM_SPOT", "DIESEL"},
        )
        self.assertEqual(commodities["URANIUM_SPOT"]["name"], "Uranium")
        self.assertEqual(commodities["URANIUM_SPOT"]["unit"], "/lb")
        self.assertEqual(commodities["WTI"]["name"], "Crude Oil")
        self.assertNotEqual(commodities["WTI"]["name"], "Crude Oil WTI")
        self.assertEqual(commodities["DIESEL"]["name"], "Diesel")
        self.assertEqual(commodities["DIESEL"]["unit"], "/bbl")

    @patch("generate.fetch_diesel", return_value={"price": 185.0, "change": 1.0})
    @patch("generate.fetch_yahoo_commodity_fallback")
    @patch("generate.scrape_page_text", return_value="valid but incomplete table")
    def test_partial_investing_table_fills_missing_core_quotes(
        self, _scrape, yahoo_fallback, _diesel
    ):
        yahoo_fallback.return_value = {
            key: {"price": price, "change": 1.0, "source": "Yahoo Finance fallback"}
            for key, price in {
                "GOLD": 4400.0,
                "SILVER": 67.0,
                "COPPER": 6.7,
                "WTI": 86.0,
            }.items()
        }

        commodities = generate.fetch_commodities()

        for key in ("GOLD", "SILVER", "COPPER", "WTI"):
            self.assertGreater(commodities[key]["price"], 0, key)
            self.assertEqual(commodities[key]["source"], "Yahoo Finance fallback")

    def test_scrape_rejects_firecrawl_block_page_and_uses_free_extract(self):
        blocked = Mock(status_code=200)
        blocked.json.return_value = {"data": {"markdown": "403"}}
        with patch.dict(os.environ, {
            "FIRECRAWL_API_URL": "http://127.0.0.1:3002",
            "FIRECRAWL_API_KEY": "paid-key-must-not-be-used",
        }, clear=True), patch("generate.requests.post", return_value=blocked) as post, \
                patch("generate._free_extract_live_page", return_value="") as free:
            self.assertEqual(generate.scrape_page_text("https://www.investing.com/example"), "")
            self.assertEqual(generate.scrape_page_text("https://www.investing.com/other"), "")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(free.call_count, 2)
        self.assertEqual(post.call_args.kwargs["timeout"], (2, 8))
        self.assertNotIn("api.firecrawl.dev", post.call_args.args[0])

    def test_free_extract_has_true_wall_clock_deadline_against_hanging_server(self):
        class HangingHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                time.sleep(10)

            def log_message(self, format, *args):
                pass

        class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        with Server(("127.0.0.1", 0), HangingHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_address[1]}/hang"
            started = time.monotonic()
            with patch.dict(os.environ, {
                "SIGNAL_FREE_EXTRACT_IO_TIMEOUT_SECONDS": "30",
                "SIGNAL_FREE_EXTRACT_DEADLINE_SECONDS": "0.5",
            }, clear=False):
                self.assertEqual(generate._free_extract_live_page(url), "")
            elapsed = time.monotonic() - started
            self.assertGreaterEqual(elapsed, 0.4)
            self.assertLess(elapsed, 2.0)

    def test_free_extract_uses_vendored_helper_for_live_page(self):
        content = "live market page " * 20

        class LiveHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = f"<html><title>Live</title><body>{content}</body></html>".encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        with socketserver.TCPServer(("127.0.0.1", 0), LiveHandler) as server:
            thread = threading.Thread(target=server.handle_request, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_address[1]}/live"
            self.assertIn("live market page", generate._free_extract_live_page(url))

    def test_paid_firecrawl_is_opt_in_and_bounded(self):
        blocked = Mock(status_code=200)
        blocked.json.return_value = {"data": {"markdown": "403"}}
        paid = Mock(status_code=200)
        paid.json.return_value = {"data": {"markdown": "| sufficiently long live markdown table row |"}}
        with patch.dict(os.environ, {
            "FIRECRAWL_API_KEY": "paid-key",
            "SIGNAL_ALLOW_PAID_FIRECRAWL": "1",
        }, clear=True), patch("generate.requests.post", side_effect=[blocked, paid]) as post:
            text = generate.scrape_page_text("https://www.investing.com/example")
        self.assertIn("live markdown", text)
        self.assertEqual(post.call_count, 2)
        self.assertTrue(all(call.kwargs["timeout"] == (2, 8) for call in post.call_args_list))
        self.assertIn("api.firecrawl.dev", post.call_args_list[-1].args[0])

    def test_market_futures_still_return_when_investing_is_unavailable(self):
        yahoo = Mock()
        yahoo.json.return_value = {
            "chart": {"result": [{"meta": {"regularMarketTime": 20}, "timestamp": [10, 20],
                "indicators": {"quote": [{"close": [100.0, 101.0]}]}}]}
        }
        with patch("generate.fetch_investing_futures", side_effect=TimeoutError), \
                patch("generate.requests.get", return_value=yahoo):
            quotes = generate.fetch_market_futures()
        self.assertEqual(set(quotes), set(generate.MARKET_FUTURES))
        self.assertTrue(all(q["price"] == 101.0 for q in quotes.values()))
        self.assertTrue(all(q["source"].startswith("Yahoo Finance") for q in quotes.values()))

    def test_rbob_crack_uses_aligned_adjacent_bars_and_42_gallons_per_barrel(self):
        rbob = {"chart": {"result": [{"timestamp": [1786507200, 1786593600, 1786680000], "indicators": {"quote": [{"close": [2.50, 2.60, 2.70]}]}}]}}
        wti = {"chart": {"result": [{"timestamp": [1786507248, 1786593648, 1786680048], "indicators": {"quote": [{"close": [80.0, 82.0, 84.0]}]}}]}}
        quote = generate.parse_rbob_crack(rbob, wti)
        self.assertAlmostEqual(quote["price"], 29.4)
        self.assertAlmostEqual(quote["previous"], 27.2)
        self.assertAlmostEqual(quote["change"], (29.4 - 27.2) / 27.2 * 100)
        self.assertEqual(quote["formula"], "RBOB × 42 − WTI")


if __name__ == "__main__":
    unittest.main()
