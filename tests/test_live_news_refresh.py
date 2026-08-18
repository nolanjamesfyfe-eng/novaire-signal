import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_fetch_feed():
    spec = importlib.util.spec_from_file_location("fetch_feed", ROOT / "scripts" / "fetch_feed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveNewsRefreshTests(unittest.TestCase):
    def test_signal_pool_keeps_four_ranked_pages_of_three(self):
        module = load_fetch_feed()
        self.assertEqual(module.SIGNAL_POOL_SIZE, 12)
        source = (ROOT / "scripts" / "fetch_feed.py").read_text(encoding="utf-8")
        self.assertIn("n=SIGNAL_POOL_SIZE", source)
        self.assertIn("top12_engagement_no_economist", source)

    def test_homepage_has_independent_refresh_controls_for_each_feed(self):
        source = (ROOT / "generate.py").read_text(encoding="utf-8")
        self.assertIn('id="news-refresh"', source)
        self.assertIn('id="signal-refresh"', source)
        self.assertIn('onclick="refreshZeroHedge(true)"', source)
        self.assertIn('onclick="refreshSignals(true)"', source)
        self.assertNotIn("Refresh both", source)
        self.assertIn("nextBatch(signalPool, signalCursor, 3)", source)
        self.assertIn("nextBatch(zhPool, zhCursor, 3)", source)
        self.assertIn("/api/zerohedge?", source)
        self.assertIn("cache: 'no-store'", source)

    def test_zerohedge_edge_api_returns_a_live_article_pool(self):
        source = (ROOT / "api" / "zerohedge.js").read_text(encoding="utf-8")
        self.assertIn("feeds.feedburner.com/zerohedge/feed", source)
        self.assertIn("articles.slice(0, 12)", source)
        self.assertIn("no-store", source)


if __name__ == "__main__":
    unittest.main()
