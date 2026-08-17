import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_finances.py"
spec = importlib.util.spec_from_file_location("generate_finances", MODULE_PATH)
assert spec is not None and spec.loader is not None
finance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finance)


class FinancesGeneratorTests(unittest.TestCase):
    def test_seed_and_projection_boundary(self):
        payload = finance.build_payload()
        self.assertEqual(21, len(payload["rows"]))
        self.assertEqual(58000, payload["rows"][0]["total_debt"])
        self.assertEqual(763, payload["rows"][0]["total_interest"])
        self.assertEqual("CAD", payload["currency"])
        self.assertTrue(all(r["status"] == "actual" for r in payload["rows"][:8]))
        self.assertTrue(all(r["status"] == "projection" for r in payload["rows"][8:]))
        self.assertEqual("2026-08-01", payload["current_period"])

    def test_generator_outputs_self_contained_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            html_path, json_path = finance.generate(Path(tmp))
            html = html_path.read_text()
            payload = json.loads(json_path.read_text())
            self.assertIn("Interest fire intensity", html)
            self.assertIn("window.OnTheRiseFinances", html)
            self.assertIn("setCurrentPeriod", html)
            self.assertIn("prefers-reduced-motion", html)
            self.assertNotIn("<script src=", html)
            self.assertNotIn("<link rel=\"stylesheet\"", html)
            self.assertEqual(finance.SHEET_ID, payload["source"]["google_sheet_id"])

    def test_battery_math_full_only_at_zero(self):
        def charge(total):
            paid = max(0, min(finance.STARTING_DEBT, finance.STARTING_DEBT - total))
            return paid / finance.STARTING_DEBT * 100
        self.assertEqual(0, charge(58000))
        self.assertLess(charge(1), 100)
        self.assertEqual(100, charge(0))

    def test_rejects_unknown_current_period(self):
        with self.assertRaises(ValueError):
            finance.build_payload("2030-01-01")


if __name__ == "__main__":
    unittest.main()
