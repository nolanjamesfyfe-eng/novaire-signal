import importlib.util
import unittest
from datetime import datetime, timezone
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
        source = (ROOT / "scripts" / "fetch_feed.py").read_text()
        self.assertIn("n=SIGNAL_POOL_SIZE", source)
        self.assertIn("top12_engagement_no_economist", source)
        self.assertIn("xurl", source)
        self.assertNotIn("nitter.net", source)

    def test_xurl_payload_skips_retweets_and_keeps_originals(self):
        module = load_fetch_feed()
        payload = {"data": [
            {"id": "1", "text": "RT @other: skip me", "created_at": "2026-08-26T03:00:00.000Z",
             "public_metrics": {"like_count": 9, "retweet_count": 9}},
            {"id": "2", "text": "JUST IN: original signal", "created_at": "2026-08-26T03:42:00.000Z",
             "public_metrics": {"like_count": 10, "retweet_count": 4}},
        ]}
        tweets = module.tweets_from_xurl_payload(payload, "WatcherGuru")
        self.assertEqual(len(tweets), 1)
        self.assertEqual(tweets[0]["id"], "2")
        self.assertEqual(tweets[0]["likes"], 10)
        self.assertEqual(tweets[0]["retweets"], 4)
        self.assertEqual(tweets[0]["url"], "https://x.com/WatcherGuru/status/2")

    def test_sparse_signal_refresh_cannot_replace_top_three_pool(self):
        module = load_fetch_feed()
        self.assertEqual(module.MIN_PUBLISHABLE_POSTS, 3)
        self.assertFalse(module.is_publishable_feed([{}, {}]))
        self.assertTrue(module.is_publishable_feed([{}, {}, {}]))

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

    def test_thai_news_prefers_last_24h_over_yesterdays_leftover(self):
        import generate
        now = datetime(2026, 8, 26, 4, 20, tzinfo=timezone.utc)
        headlines = [
            {
                "title": "Two Swedes arrested in Bangkok Immigration Bureau police operation on Sunday after they fled Koh Samui",
                "url": "https://www.thaiexaminer.com/thai-news-foreigners/2026/08/24/two-swedes/",
                "source": "Thai Examiner",
                "summary": "A Swedish fugitive wanted over attempted murder is seized outside a luxury Bangkok condo.",
                "score": 30,
                "published_at": datetime(2026, 8, 24, 17, 53, tzinfo=timezone.utc),
            },
            {
                "title": "Tourists to be briefed on Thai laws before departure. Minister says Israeli man’s visa has been cancelled",
                "url": "https://www.thaiexaminer.com/thai-news-foreigners/2026/08/25/tourists-briefed/",
                "source": "Thai Examiner",
                "summary": "New tourist briefing and a cancelled visa after a Koh Samui zoo dispute.",
                "score": 18,
                "published_at": datetime(2026, 8, 25, 16, 6, tzinfo=timezone.utc),
            },
            {
                "title": "Foreigners given a say on tourism fee as cabinet studies the airport surcharge",
                "url": "https://www.bangkokpost.com/thailand/general/foreigners-tourism-fee",
                "source": "Bangkok Post",
                "summary": "Cabinet lets foreigners comment on the planned tourism fee.",
                "score": 16,
                "published_at": datetime(2026, 8, 26, 4, 33, tzinfo=timezone.utc),
            },
        ]
        selected = generate.select_thai_news(headlines, now=now)
        titles = [item["title"] for item in selected]
        self.assertTrue(titles)
        self.assertIn("Foreigners given a say on tourism fee", titles[0])
        self.assertNotIn("Two Swedes arrested", titles[0])
        self.assertTrue(all("Two Swedes" not in title for title in titles))


if __name__ == "__main__":
    unittest.main()
