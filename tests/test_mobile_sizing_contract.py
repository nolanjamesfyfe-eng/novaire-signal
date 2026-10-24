import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MobileSizingContractTests(unittest.TestCase):
    def test_generator_and_output_restore_phone_desktop_site_canvas(self):
        source = (ROOT / "generate.py").read_text(encoding="utf-8")
        output = (ROOT / "index.html").read_text(encoding="utf-8")
        for text in (source, output):
            self.assertIn('(hover:none) and (min-width:601px) and (max-width:1100px)', text)
            self.assertIn('zoom:2', text)
            self.assertIn('grid-template-columns:repeat(2,1fr)', text)
            self.assertIn('grid-template-columns:repeat(3,minmax(0,1fr))', text)
            self.assertIn('grid-template-columns:repeat(4,1fr)', text)

    def test_true_mobile_and_desktop_contracts_remain_present(self):
        source = (ROOT / "generate.py").read_text(encoding="utf-8")
        self.assertIn('@media(min-width:900px){{body{{zoom:1.1}}}}', source)
        self.assertIn('@media(max-width:600px){{', source)
        self.assertIn('.anki-panel-link{{width:49.0078125px;height:14.8125px', source)
        self.assertIn('.card.google-tasks-card{{padding:0}}', source)


if __name__ == "__main__":
    unittest.main()
