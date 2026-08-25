import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import generate


class YoutubeMetricIntegrityTests(unittest.TestCase):
    def test_watch_page_parser_refreshes_views_and_likes(self):
        response = Mock()
        response.text = (
            '"videoViewCountRenderer":{"viewCount":{"simpleText":"1,234 views"}} '
            '"accessibilityText":"like this video along with 56 other people"'
        )
        response.raise_for_status.return_value = None
        item = {"title": "Clip", "url": "https://www.youtube.com/watch?v=abc", "views": 10, "likes": 1}
        with patch.object(generate.requests, "get", return_value=response):
            refreshed = generate.fetch_youtube_watch_metrics(item)
        self.assertEqual(refreshed["views"], 1234)
        self.assertEqual(refreshed["likes"], 56)

    def test_verified_cache_requires_both_metrics_on_both_cards(self):
        valid = {
            "clip": {"title": "Clip", "url": "https://www.youtube.com/watch?v=abc", "views": 55, "likes": 2},
            "episode": {"title": "Episode", "url": "https://www.youtube.com/watch?v=def", "views": 62, "likes": 6},
        }
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "youtube.json"
            generate.save_latest_youtube(valid, path=str(path))
            loaded = generate.load_latest_youtube(path=str(path))
            self.assertEqual(loaded["clip"]["views"], 55)
            broken = json.loads(path.read_text())
            broken["episode"]["likes"] = None
            path.write_text(json.dumps(broken))
            self.assertEqual(generate.load_latest_youtube(path=str(path)), {})


if __name__ == "__main__":
    unittest.main()
