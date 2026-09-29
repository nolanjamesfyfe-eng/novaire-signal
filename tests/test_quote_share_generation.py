import unittest
from unittest.mock import patch
import generate


class QuoteShareGenerationTest(unittest.TestCase):
    def test_render_html_preserves_two_direct_share_hooks(self):
        holding = [{"ticker": "T.X", "display": "T", "name": "Fixture", "shares": 1, "currency": "USD", "sector": "Other"}]
        with patch.object(generate, "fetch_radar_moonshots", return_value={}), \
             patch.object(generate, "show_biweekly_monday_section", return_value=False), \
             patch.object(generate, "fetch_live_instagram_metrics", side_effect=lambda item: item):
            html = generate.render_html({}, [], [], {}, {}, {}, {}, {"usdcad": 1.3}, {}, {}, {},
                                        holdings_source=holding, market_futures=[], market_indices=[])
        for hook in ('id="med-share-trigger"', 'data-share-kind="meditation"',
                     'id="quote-share-trigger"', 'data-share-kind="quote"',
                     'id="quote-share-dialog"', 'id="quote-share-canvas"',
                     'id="quote-post-preview"', '/quote-studio/integrated.css',
                     '/quote-studio/integrated.js', '/quote-studio/bolt.svg'):
            self.assertIn(hook, html)
        self.assertNotIn('id="med-collapse"', html)
        self.assertNotIn('Collapse meditation', html)
        self.assertNotIn('id="quote-post-review"', html)
        self.assertIn('id="meditation-daily" class="meditation"', html)
        self.assertIn('<summary>', html)
        self.assertEqual(html.count('M219 44Q217 43 215 44L51 180Q49 183'), 2)
        self.assertNotIn('STOIC PHILOSOPHER', html)

    def test_separate_quotes_body_is_build_time_content_not_js_placeholder(self):
        holding = [{"ticker": "T.X", "display": "T", "name": "Fixture", "shares": 1, "currency": "USD", "sector": "Other"}]
        with patch.object(generate, "fetch_radar_moonshots", return_value={}), \
             patch.object(generate, "show_biweekly_monday_section", return_value=False), \
             patch.object(generate, "fetch_live_instagram_metrics", side_effect=lambda item: item):
            html = generate.render_html({}, [], [], {}, {}, {}, {}, {"usdcad": 1.3}, {}, {}, {},
                                        holdings_source=holding, market_futures=[], market_indices=[])
        for slot in ("qt-type", "qt-text", "qt-auth"):
            match = __import__('re').search(rf'id="{slot}">([^<]+)</div>', html)
            self.assertIsNotNone(match, slot)
            self.assertTrue(match.group(1).strip(), slot)
        self.assertIn("const DAILY_QUOTE =", html)
        self.assertNotIn('id="qt-text"></div>', html)

    def test_quote_build_guard_rejects_empty_slots(self):
        with self.assertRaisesRegex(ValueError, "empty or unreadable"):
            generate.quote_entries_from_js('[{text:"", author:"Nobody"}]')


if __name__ == '__main__':
    unittest.main()
