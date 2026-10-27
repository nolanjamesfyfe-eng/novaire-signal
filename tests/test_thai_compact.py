import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from bs4 import BeautifulSoup
import generate as g

class ThaiCompactTests(unittest.TestCase):
    def test_xml_dates_are_not_lost_to_html_lowercasing(self):
        from email.utils import format_datetime
        published = datetime.now(timezone.utc).replace(microsecond=0)
        xml = '<rss><channel>' + ''.join(f'<item><title>Bangkok immigration police visa crackdown {i}</title><link>https://thethaiger.com/news/visa-{i}</link><pubDate>{format_datetime(published)}</pubDate><description>Police report immigration enforcement in Bangkok.</description></item>' for i in range(3)) + '</channel></rss>'
        class Response:
            text = xml
            def raise_for_status(self): pass
        with patch.object(g.requests, 'get', return_value=Response()), patch.object(g, 'fetch_thai_og_image', return_value=''):
            items = g.fetch_bangkok_post()
        self.assertEqual(len(items), 3)
        self.assertEqual(len({i['url'] for i in items}), 3)
        self.assertTrue(all(i['published_at'] == published for i in items))

    def test_sparse_fresh_pool_fills_from_dated_48h_not_unknown_or_ads(self):
        now = datetime.now(timezone.utc)
        items = [dict(title=f'Visa story {i}', url=f'https://thethaiger.com/news/{i}', score=20, published_at=now-timedelta(hours=h)) for i,h in enumerate([2,30,40,80])]
        items.append(dict(title='Unknown story',url='https://thethaiger.com/news/unknown',score=99,published_at=None))
        selected = g.select_thai_news(items,now)
        self.assertEqual([i['title'] for i in selected], ['Visa story 0','Visa story 1','Visa story 2'])
        self.assertEqual(g.select_thai_news(items[3:],now), [])
        self.assertEqual(g.select_thai_news([items[0],items[0],items[1]],now).__len__(), 2)

    def test_render_is_bounded_escaped_with_pinned_footer_and_dates(self):
        cards = g.render_thai_news_cards([dict(title='Visa <script> & safety ' * 30, summary='Real publisher <copy> & text ' * 30, source='The Thaiger', url='https://thethaiger.com/news/visa', published_at=datetime(2026,10,27,tzinfo=timezone.utc))])
        soup = BeautifulSoup(cards, 'html.parser')
        card = soup.select_one('.thai-feed-card')
        self.assertIn('zh-feed-card', card['class'])
        self.assertLessEqual(len(card.select_one('.feed-card-title').text),110)
        self.assertLessEqual(len(card.select_one('.feed-card-excerpt').text),140)
        self.assertIs(card.select_one('.feed-card-source').parent,card)
        self.assertIsNotNone(card.select_one('.feed-card-body'))
        self.assertFalse(soup.select('script'))
        self.assertEqual(card['data-published-at'], '2026-10-27T00:00:00+00:00')
        self.assertIn('No image', card.get('data-image-status','No image'))

    def test_advertorial_and_undated_feeds_do_not_fill_slots(self):
        class Response:
            text = '<rss><channel><item><title>Best tailor in Bangkok for expat tourists</title><link>https://thethaiger.com/guides/best-tailor</link><pubDate>Tue, 27 Oct 2026 01:00:00 +0000</pubDate></item><item><title>Visa enforcement unknown publication date</title><link>https://thethaiger.com/news/undated</link></item></channel></rss>'
            def raise_for_status(self): pass
        with patch.object(g.requests, 'get', return_value=Response()):
            self.assertEqual(g.fetch_bangkok_post(), [])
        with patch.object(g.requests, 'get', side_effect=RuntimeError('publisher unavailable')):
            self.assertEqual(g.fetch_bangkok_post(), [])

    def test_unavailable_is_not_a_fake_story(self):
        self.assertNotIn('<article',g.render_thai_news_cards([]))
        self.assertIn('unavailable',g.render_thai_news_cards([]))

if __name__ == '__main__': unittest.main()
