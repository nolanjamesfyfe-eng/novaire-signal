import copy
import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

import generate

ROOT = Path(__file__).resolve().parents[1]


def load_fetch_feed():
    spec = importlib.util.spec_from_file_location("fetch_feed_cards", ROOT / "scripts" / "fetch_feed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ZH_RSS = """<?xml version="1.0"?><rss><channel><item>
<title>Markets &amp; &lt;script&gt;alert(1)&lt;/script&gt;</title>
<link>https://www.zerohedge.com/markets/example</link>
<pubDate>Fri, 23 Oct 2026 09:00:00 +0000</pubDate>
<description><![CDATA[
<p><em>Authored by A Person via Example.com,</em></p>
<p>Stocks moved higher after the opening bell. This second sentence must not render.</p>
<img src="https://assets.zerohedge.com/s3fs-public/inline-images/chart.jpg" alt="Market chart">
]]></description></item></channel></rss>"""


class CompactFeedCardTests(unittest.TestCase):
    def test_zerohedge_rss_propagates_sourced_excerpt_and_genuine_image(self):
        articles = generate.parse_zerohedge_feed(ZH_RSS, limit=12)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["excerpt"], "Stocks moved higher after the opening bell.")
        self.assertEqual(articles[0]["image"], "https://assets.zerohedge.com/s3fs-public/inline-images/chart.jpg")
        self.assertEqual(articles[0]["image_alt"], "Market chart")

    def test_zerohedge_renderer_escapes_copy_and_uses_fixed_lazy_image(self):
        html = generate.render_zerohedge_cards(generate.parse_zerohedge_feed(ZH_RSS))
        self.assertIn("Markets &amp; &lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn('loading="lazy"', html)
        self.assertIn('width="80" height="60"', html)
        self.assertIn('class="feed-thumb"', html)
        self.assertIn("Stocks moved higher after the opening bell.", html)

    def test_bad_or_missing_image_gracefully_renders_text_only(self):
        item = {
            "title": "Text only",
            "url": "https://www.zerohedge.com/markets/text-only",
            "excerpt": "A sourced sentence.",
            "image": "https://evil.example/tracker.png",
        }
        html = generate.render_zerohedge_cards([item])
        self.assertNotIn("evil.example", html)
        self.assertNotIn("feed-thumb", html)
        self.assertIn("feed-card--text-only", html)

    def test_x_metadata_enrichment_preserves_original_rank_ids_and_scores(self):
        module = load_fetch_feed()
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        fixture = [[
            {"id": "a", "handle": "one", "text": "one full post", "likes": 5, "retweets": 2, "createdAtMs": now_ms - 1000},
            {"id": "b", "handle": "two", "text": "two full post", "likes": 9, "retweets": 1, "createdAtMs": now_ms - 2000},
            {"id": "c", "handle": "three", "text": "three full post", "likes": 6, "retweets": 2, "createdAtMs": now_ms - 3000},
        ]]
        ranked = module.top_engagement(fixture, set(), module.ENGAGEMENT_MAX_AGE_MS, 3)
        for index, post in enumerate(ranked):
            post["slot_order"] = index + 1
            post["engagementScore"] = post["likes"] + post["retweets"]
        before = [(p["id"], p["slot_order"], p["engagementScore"]) for p in ranked]
        enriched = module.enrich_selected_posts(
            copy.deepcopy(ranked),
            metadata_fetcher=lambda post: {
                "text": post["text"] + " — complete sourced ending",
                "views": 1234,
                "media_url": f"https://pbs.twimg.com/media/{post['id']}.jpg",
                "media_alt": "Attached image",
            },
        )
        after = [(p["id"], p["slot_order"], p["engagementScore"]) for p in enriched]
        self.assertEqual(before, after)
        self.assertEqual([p["id"] for p in enriched], ["b", "c", "a"])
        self.assertTrue(all(p["text"].endswith("complete sourced ending") for p in enriched))
        self.assertTrue(all(p["views"] == 1234 for p in enriched))
        self.assertTrue(all(p["media_url"].startswith("https://pbs.twimg.com/media/") for p in enriched))

    def test_fixed_metadata_endpoint_requires_matching_post_and_safe_media(self):
        module = load_fetch_feed()
        payload = {"tweet": {
            "id": "123",
            "text": "The complete post text.",
            "views": 99,
            "media": {"photos": [
                {"url": "https://evil.example/fake.jpg"},
                {"url": "https://pbs.twimg.com/media/REAL.jpg"},
            ]},
        }}
        metadata = module.parse_fx_public_metadata(payload, "123")
        self.assertEqual(metadata["text"], "The complete post text.")
        self.assertEqual(metadata["views"], 99)
        self.assertEqual(metadata["media_url"], "https://pbs.twimg.com/media/REAL.jpg")
        self.assertEqual(module.parse_fx_public_metadata(payload, "999"), {})

    def test_x_metadata_parser_rejects_arbitrary_images(self):
        module = load_fetch_feed()
        page = r'''<meta property="og:title" content="Name (@handle) on X">
        media_url_https\":\"https://pbs.twimg.com/media/REAL.jpg\"
        media_url_https\":\"https://evil.example/fake.jpg\"'''
        metadata = module.parse_x_public_metadata(page)
        self.assertEqual(metadata["media_url"], "https://pbs.twimg.com/media/REAL.jpg")
        self.assertNotIn("evil.example", str(metadata))

    def test_generated_renderer_is_three_across_full_text_and_mobile_snap(self):
        source = (ROOT / "generate.py").read_text(encoding="utf-8")
        for marker in (
            ".feed-card-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))",
            "white-space:pre-wrap",
            "overflow-wrap:anywhere",
            "scroll-snap-type:x mandatory",
            "renderFeed(signalBatch.items)",
            "renderZeroHedge(batch.items)",
            "safeImageUrl",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("text-overflow:ellipsis", source[source.index(".compact-feed-card"):source.index(".fed-card")])

    def test_x_cards_are_three_quarters_of_zerohedge_with_visible_footer(self):
        source = (ROOT / "generate.py").read_text(encoding="utf-8")
        feed_css = source[source.index(".compact-feed-card"):source.index(".fed-card")]
        for marker in (
            "--zerohedge-card-height:260px",
            "--signal-card-height:195px",
            ".zh-feed-card{{box-sizing:border-box;height:var(--zerohedge-card-height)",
            ".signal-feed-card{{box-sizing:border-box;height:var(--signal-card-height)",
            ".signal-feed-card .feed-card-body{{flex:1 1 auto;min-height:0;overflow:hidden",
            ".signal-feed-card .feed-card-copy{{min-height:0;overflow:hidden",
            "display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:9;overflow:hidden",
            "--zerohedge-card-height:140px;--signal-card-height:105px",
            "-webkit-line-clamp:3",
            ".feed-metrics{{flex:none",
        ):
            self.assertIn(marker, feed_css)

        self.assertEqual(195 / 260, 0.75)
        self.assertEqual(105 / 140, 0.75)


if __name__ == "__main__":
    unittest.main()
