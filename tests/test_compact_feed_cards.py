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
    def test_current_publisher_cms_images_are_allowed_without_widening_to_arbitrary_hosts(self):
        rss = ZH_RSS.replace('assets.zerohedge.com/s3fs-public', 'cms.zerohedge.com/sites/default/files')
        articles = generate.parse_zerohedge_feed(rss)
        self.assertIn('https://cms.zerohedge.com/', articles[0]['image'])
        self.assertIn('https://cms.zerohedge.com/', generate.render_zerohedge_cards(articles))
        for host in ['evil.example', 'cms.zerohedge.com.evil.example']:
            self.assertEqual(generate.parse_zerohedge_feed(rss.replace('cms.zerohedge.com', host))[0]['image'], '')

    def test_feed_disclosures_use_stable_exact_choice_not_daily_reset(self):
        from bs4 import BeautifulSoup
        html = (ROOT / 'index.html').read_text()
        soup = BeautifulSoup(html, 'html.parser')
        for card_id, key in [('zerohedge-card', 'nv_zerohedge_state'), ('signal-feed-card', 'nv_signal_feed_state')]:
            card = soup.find(id=card_id)
            self.assertEqual(card.name, 'details')
            self.assertIsNotNone(card.find('summary', recursive=False))
            self.assertNotIn('data-daily-edition', card.attrs)
            self.assertIn(f"rememberFixedAccordion('{card_id}', '{key}')", html)
            self.assertIsNone(card.summary.find('button'))

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

    def test_zerohedge_copy_uses_word_safe_unicode_caps_and_preserves_full_title_accessibly(self):
        full_title = "⚡ " + "Markets rally on sourced evidence " * 8 + "終"
        full_excerpt = "Investors weigh the original publisher sentence " * 8 + "終"
        item = {
            "title": full_title,
            "url": "https://www.zerohedge.com/markets/long-copy",
            "excerpt": full_excerpt,
            "image": "",
        }
        html = generate.render_zerohedge_cards([item])
        self.assertIn('data-title-limit="110"', html)
        self.assertIn('data-excerpt-limit="140"', html)
        self.assertIn(f'title="{generate.escape(full_title, quote=True)}"', html)
        self.assertIn(f'aria-label="{generate.escape(full_title, quote=True)}"', html)
        visible_title = generate.truncate_word_safe(full_title, generate.ZEROHEDGE_TITLE_CHAR_LIMIT)
        visible_excerpt = generate.truncate_word_safe(full_excerpt, generate.ZEROHEDGE_EXCERPT_CHAR_LIMIT)
        self.assertLessEqual(len(visible_title), 110)
        self.assertLessEqual(len(visible_excerpt), 140)
        self.assertTrue(visible_title.endswith("…"))
        self.assertTrue(visible_excerpt.endswith("…"))
        self.assertNotIn(" …", visible_title)
        self.assertIn(generate.escape(visible_title), html)
        self.assertIn(generate.escape(visible_excerpt), html)

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

    def test_zerohedge_density_override_preserves_shared_thai_and_x_geometry(self):
        html = generate.render_zerohedge_cards(generate.parse_zerohedge_feed(ZH_RSS))
        from bs4 import BeautifulSoup
        card = BeautifulSoup(html, 'html.parser').select_one('.zh-feed-card')
        header = card.select_one('.zh-story-header')
        self.assertIsNotNone(header.select_one('.feed-card-title'))
        self.assertIsNotNone(header.select_one('.feed-card-media'))
        self.assertIsNone(header.select_one('.feed-card-excerpt'))
        self.assertEqual(header.find_next_sibling().get('class'), ['feed-card-excerpt'])
        source = (ROOT / 'generate.py').read_text()
        self.assertIn('#zerohedge-feed .zh-feed-card{{height:auto;min-height:0;gap:6px}}', source)
        self.assertIn('#zerohedge-feed .feed-card-excerpt{{margin:0;width:100%;-webkit-line-clamp:3;color:var(--dim)}}', source)
        self.assertIn('class="zh-story-header">${{media}}', source)

        source = (ROOT / "generate.py").read_text(encoding="utf-8")
        feed_css = source[source.index(".compact-feed-card"):source.index(".fed-card")]
        for marker in (
            "--feed-card-height:195px",
            ".zh-feed-card,.signal-feed-card{{box-sizing:border-box;height:var(--feed-card-height)",
            ".zh-feed-card{{flex-direction:column;gap:6px",
            ".zh-feed-card .feed-card-body{{flex:1 1 auto;min-height:0;overflow:hidden",
            ".zh-feed-card .feed-card-copy{{min-height:0;overflow:hidden",
            ".zh-feed-card .feed-card-source{{flex:none;margin-top:0",
            ".signal-feed-card{{flex-direction:column;gap:6px",
            ".signal-feed-card .feed-card-body{{flex:1 1 auto;min-height:0;overflow:hidden",
            ".signal-feed-card .feed-card-copy{{min-height:0;overflow:hidden",
            "display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:9;overflow:hidden",
            "--feed-card-height:105px",
            ".zh-feed-card .feed-card-title{{-webkit-line-clamp:2",
            ".zh-feed-card .feed-card-excerpt{{-webkit-line-clamp:1",
            "-webkit-line-clamp:3",
            ".feed-metrics{{flex:none",
        ):
            self.assertIn(marker, feed_css)

        renderer = source[source.index("function renderZeroHedge"):source.index("async function refreshSignals")]
        self.assertIn("truncateWordSafe(item.title, ZEROHEDGE_TITLE_CHAR_LIMIT)", renderer)
        self.assertIn("truncateWordSafe(normalizeArticleText(item.excerpt), ZEROHEDGE_EXCERPT_CHAR_LIMIT)", renderer)
        self.assertIn('class=\"feed-card-body\"', renderer)
        self.assertIn('class=\"feed-card-source\"', renderer)


if __name__ == "__main__":
    unittest.main()
