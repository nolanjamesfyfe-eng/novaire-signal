import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate  # noqa: E402

NOW = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)


class SocialVideoArchiveTests(unittest.TestCase):
    def test_videos_older_than_30_days_archive(self):
        self.assertTrue(generate.social_video_archived({"published_at": "Sep 22, 2026"}, now=NOW))
        self.assertTrue(generate.social_video_archived({"published_at": "Jul 31, 2026"}, now=NOW))
        self.assertTrue(generate.social_video_archived({"published_at": "2026-09-01T00:00:00+00:00"}, now=NOW))

    def test_recent_videos_stay(self):
        self.assertFalse(generate.social_video_archived({"published_at": "Sep 26, 2026"}, now=NOW))
        self.assertFalse(generate.social_video_archived({"published_at": "2026-10-23T03:09:47+00:00"}, now=NOW))

    def test_unknown_dates_are_not_hidden(self):
        self.assertFalse(generate.social_video_archived({"published_at": None}, now=NOW))
        self.assertFalse(generate.social_video_archived({}, now=NOW))
        self.assertFalse(generate.social_video_archived(None, now=NOW))


if __name__ == "__main__":
    unittest.main()
