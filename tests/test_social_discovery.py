import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

import social_discovery as social


class SocialDiscoveryTests(unittest.TestCase):
    def test_youtube_tab_requires_verified_channel_identity(self):
        response = Mock()
        response.text = '<link rel="canonical" href="https://www.youtube.com/channel/wrong"><script>"videoId":"abcdefghijk"</script>'
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            social.discover_youtube_channel("j_novaire", session=session)

    def test_short_tab_without_short_lockup_is_honestly_empty(self):
        self.assertIsNone(social._first_video_id('"videoId":"abcdefghijk"', shorts=True))

    def test_failed_refresh_preserves_complete_dated_snapshot(self):
        snapshot = {
            "instagram": {"url": "https://www.instagram.com/reel/abc/", "verified_at": "2026-09-08T00:00:00Z"},
            "youtube": {
                key: {
                    "channel_id": channel["channel_id"], "verified_at": "2026-09-08T00:00:00Z",
                    "video": {"title": "Verified", "url": "https://www.youtube.com/watch?v=abcdefghijk"},
                    "short": None,
                }
                for key, channel in social.CHANNELS.items()
            },
        }
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "social.json"
            social.save_cache(snapshot, path)
            broken = Mock()
            broken.get.side_effect = RuntimeError("offline")
            result = social.discover_all(path, session=broken)
        self.assertEqual(result["instagram"]["verified_at"], "2026-09-08T00:00:00Z")
        self.assertEqual(result["youtube"]["j_novaire"]["video"]["title"], "Verified")


if __name__ == "__main__":
    unittest.main()
