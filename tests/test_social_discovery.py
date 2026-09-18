import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

import social_discovery as social


class SocialDiscoveryTests(unittest.TestCase):
    def _instagram(self, shortcode="owned", timestamp=200, owner_id="5776730090", username="j.novaire", is_video=True):
        return {"shortcode": shortcode, "taken_at_timestamp": timestamp, "is_video": is_video,
                "owner": {"id": owner_id, "username": username}, "edge_media_to_caption": {"edges": []}}

    def _embed_session(self, media):
        context = {"context": {"username": "j.novaire", "owner_id": 5776730090, "graphql_media": [
            {"shortcode_media": item} for item in media]}}
        encoded = json.dumps(json.dumps(context))[1:-1]
        response = Mock(text=f'contextJSON":"{encoded}"')
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response
        return session

    def test_instagram_selects_latest_owned_video_not_newer_foreign_or_photo(self):
        result = social.discover_instagram(session=self._embed_session([
            self._instagram("foreign", 400, owner_id="999", username="second.renaissance"),
            self._instagram("photo", 300, is_video=False),
            self._instagram("owned", 200),
        ]))
        self.assertEqual(result["url"], "https://www.instagram.com/reel/owned/")
        self.assertEqual(result["owner_id"], social.INSTAGRAM_OWNER_ID)

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
            "instagram": {"type": "reel", "owner_id": social.INSTAGRAM_OWNER_ID,
                          "owner_username": social.INSTAGRAM_USERNAME,
                          "url": "https://www.instagram.com/reel/abc/", "verified_at": "2026-09-08T00:00:00Z"},
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

    def test_partial_instagram_listing_cannot_regress_latest_item(self):
        identity = {"type": "reel", "owner_id": social.INSTAGRAM_OWNER_ID,
                    "owner_username": social.INSTAGRAM_USERNAME, "verified_at": "now"}
        cached = {**identity, "url": "https://www.instagram.com/reel/new/", "published_at": "2026-09-08T04:47:16+00:00"}
        candidate = {**identity, "url": "https://www.instagram.com/reel/old/", "published_at": "2026-09-07T12:44:46+00:00"}
        selected, regressed = social._keep_newest(candidate, cached)
        self.assertTrue(regressed)
        self.assertEqual(selected["url"], cached["url"])

    def test_newer_instagram_item_replaces_cache(self):
        cached = {"url": "https://www.instagram.com/reel/old/", "published_at": "2026-09-07T12:44:46+00:00"}
        candidate = {"url": "https://www.instagram.com/reel/new/", "published_at": "2026-09-08T04:47:16+00:00"}
        selected, regressed = social._keep_newest(candidate, cached)
        self.assertFalse(regressed)
        self.assertEqual(selected["url"], candidate["url"])

    def test_foreign_cached_item_can_never_override_owned_candidate(self):
        candidate = {"type": "reel", "owner_id": social.INSTAGRAM_OWNER_ID,
                     "owner_username": social.INSTAGRAM_USERNAME,
                     "url": "https://www.instagram.com/reel/owned/",
                     "published_at": "2026-09-07T00:00:00Z", "verified_at": "now"}
        contaminated = {"type": "reel", "url": "https://www.instagram.com/reel/foreign/",
                        "published_at": "2026-09-08T00:00:00Z", "verified_at": "old"}
        selected, regressed = social._keep_newest(candidate, contaminated)
        self.assertFalse(regressed)
        self.assertEqual(selected["url"], candidate["url"])


if __name__ == "__main__":
    unittest.main()
