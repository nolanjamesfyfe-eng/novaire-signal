import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_generated_quotes import validate


class GeneratedQuoteValidationTests(unittest.TestCase):
    def make_generated(self, root, *, expected, rendered):
        quotes = ''.join(
            ['<b data-crypto-price>1</b>' for _ in range(8)]
            + ['<b data-comm-price>1</b>' for _ in range(6)]
            + ['<b data-future-price>1</b>' for _ in range(3)]
        )
        (root / 'index.html').write_text(quotes, encoding='utf-8')
        (root / 'portfolio').mkdir()
        (root / 'portfolio' / 'index.html').write_text(
            '<td data-chart-symbol="X"></td>' * rendered, encoding='utf-8'
        )
        (root / 'stats.json').write_text(
            json.dumps({'portfolio': {'holdings_count': expected}}), encoding='utf-8'
        )

    def test_accepts_current_source_count_without_stale_fixed_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_generated(root, expected=19, rendered=19)
            self.assertEqual([], validate(root))

    def test_rejects_generator_dropping_a_source_holding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_generated(root, expected=19, rendered=18)
            self.assertIn('expected 19 ticker rows', validate(root)[0])

    def test_rejects_missing_source_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_generated(root, expected=None, rendered=19)
            self.assertIn('invalid generated holdings_count', validate(root)[0])


if __name__ == '__main__':
    unittest.main()