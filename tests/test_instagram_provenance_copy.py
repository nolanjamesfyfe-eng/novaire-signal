from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstagramProvenanceCopyTests(unittest.TestCase):
    def test_positive_metrics_status_is_hidden_but_verification_date_remains(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        start = html.index("INSTAGRAM · PERSONAL LATEST VIDEO")
        end = html.index("</details>", start)
        card = html[start:end]

        self.assertIn("https://www.instagram.com/reel/DeCictnNuHv/", card)
        self.assertIn("<b>3</b> likes", card)
        self.assertIn("Instagram public view count unavailable", card)
        self.assertIn("Latest check incomplete; item verified 2026-10-04", card)
        self.assertIn("verified on 2026-10-20", card)
        self.assertNotIn("public metrics available", card)

    def test_generator_only_suppresses_the_redundant_positive_status_for_instagram(self):
        source = (ROOT / "generate.py").read_text(encoding="utf-8")
        self.assertIn('metrics_status == "public metrics available"', source)
        self.assertIn('metrics_status = ""', source)
        self.assertIn('f"verified on {verified[:10]}"', source)
        self.assertIn('hide_positive_metrics_status=True', source)


if __name__ == "__main__":
    unittest.main()