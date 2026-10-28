import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone
import generate
from scripts import fetch_feed as feed


class FeedReliability(unittest.TestCase):
    def test_placeholder_and_repeated_escapes(self):
        sentence = 'Actual election results show neither bloc winning a majority.'
        for blank in ['&nbsp;', '&amp;nbsp;', '&amp;amp;nbsp;', '&#160;', '&#xA0;', '\u00a0', '   ']:
            self.assertEqual(generate._first_sourced_sentence('<p>'+blank+'</p><p>Chart: electoral seats</p><p>'+sentence+'</p>'), sentence)
            self.assertEqual(generate._first_sourced_sentence('<p>'+blank+'</p>'), '')
        self.assertEqual(generate._first_sourced_sentence('&lt;p&gt;'+sentence+'&lt;/p&gt;'), sentence)

    def test_missing_metadata_real_public_fallback(self):
        sentence = 'Actual election results show neither bloc winning a majority.'
        self.assertEqual(generate._zh_public_intro('<meta property="og:description" content="&amp;nbsp;"><article><p>&nbsp;</p><p>'+sentence+'</p></article>'), sentence)
        self.assertEqual(generate._zh_public_intro('<meta name="description" content="'+sentence+'">'), sentence)
        self.assertEqual(generate._zh_public_intro('<article><p>&nbsp;</p></article>'), '')

    def test_rank_population_order_window(self):
        now = int(datetime.now(timezone.utc).timestamp()*1000)
        def post(i,handle,likes,retweets,age):
            return dict(id=i,handle=handle,likes=likes,retweets=retweets,createdAtMs=now-age)
        rows=[post('a','one',5,5,10000),post('b','two',9,1,1000),post('c','one',20,0,2000),post('old','old',999,999,86400001),post('future','future',999,999,-100000)]
        self.assertEqual([p['id'] for p in feed.top_engagement([rows],set(),86400000,12)],['c','b'])
        ties = [post('older','older',8,2,10000),post('newer','newer',2,8,1000)]
        self.assertEqual([p['id'] for p in feed.top_engagement([ties],set(),86400000,12)], ['newer','older'])
        self.assertEqual(len(feed.ALL_ACCOUNTS),16)
        self.assertEqual(feed.SIGNAL_POOL_SIZE,12)

    def test_no_invented_metrics_or_timestamp(self):
        row={'id':'123','text':'A genuine current original post','created_at':datetime.now(timezone.utc).isoformat(),'public_metrics':{'like_count':0,'retweet_count':0}}
        self.assertEqual(len(feed.tweets_from_xurl_payload({'data':[row]},'one')),1)
        for extra in [{'created_at':''},{'created_at':'bad'},{'public_metrics':{}},{'referenced_tweets':[{'type':'retweeted'}]}]:
            self.assertEqual(feed.tweets_from_xurl_payload({'data':[{**row,**extra}]},'one'),[])

    def test_provider_failure_preserves_success_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'feed.json'
            target.write_text(json.dumps({'ok':True,'fetchedAt':'2026-09-20T00:00:00Z','posts':[{'id':'old'}]}))
            with patch.object(feed,'REPO_ROOT',Path(directory)), patch.object(feed,'x_read',return_value=({}, {'code':401,'detail':'Unauthorized'})), patch.object(feed.time,'sleep'):
                feed.main()
            result=json.loads(target.read_text())
            self.assertFalse(result['ok'])
            self.assertEqual(result['fetchedAt'],'2026-09-20T00:00:00Z')
            self.assertEqual(result['diagnostics']['accountsSucceeded'],0)
            self.assertEqual(len(result['diagnostics']['sources']),16)
            self.assertTrue(result['diagnostics']['attemptedAt'])
            self.assertEqual(result['diagnostics']['sources']['zerohedge']['error']['code'],401)

if __name__=='__main__': unittest.main()
