import csv
import io
import sys
import unittest
from unittest.mock import patch

import generate


SHEET_ROWS = [
    ["NOTES", "", "Description", "TICKER", "% change", "Exchange", "52w L", "% off 52 wL", "BUY Price $", "# of CON", "I Margin * Contracts", "USD / AUD (+/-)", "% of Fund", "$ ROI", "ROI %", "CAD"],
    ["", "CAD", "Hydrograph", "CNSX:HG", "", "$6.18", "", "", "$1.40", "9750", "$60,255.00", "", "49.64%", "", "", "Graphene"],
    ["", "CAD", "FreeGold Ventures", "FVL", "", "$1.21", "", "", "$1.35", "12450", "$15,064.50", "", "12.41%", "", "", "Gold"],
    ["", "CAD", "Global Atomic", "TSE:GLO", "", "$0.59", "", "", "$0.79", "20011", "$11,806.49", "", "9.73%", "", "", "Uranium"],
    ["", "USD", "Bannerman UR ASX", "BNNLF", "", "$2.58", "", "", "$1.70", "1300", "$3,354.00", "", "3.83%", "", "", "Uranium"],
    ["", "CAD", "Vizsla Silver", "TSE:VZLA", "", "$5.21", "", "", "$5.19", "700", "$3,647.00", "", "3.00%", "", "", "Silver"],
    ["", "CAD", "Denison", "DML", "", "$4.47", "", "", "$2.21", "750", "$3,352.50", "", "2.76%", "", "", "Uranium"],
    ["", "CAD", "Aftermath Silver", "CVE:AAG", "", "$0.76", "", "", "$0.936", "4000", "$3,040.00", "", "2.50%", "", "", "Copper"],
    ["", "CAD", "Power Nickel", "CVE:PNPN", "", "$1.26", "", "", "$1.27", "2500", "$3,150.00", "", "2.59%", "", "", "Copper"],
    ["Double", "CAD", "GreenLand Resources", "MOLY", "", "$1.38", "", "", "$1.33", "2000", "$2,760.00", "", "2.27%", "", "", "Molybdenum"],
    ["", "CAD", "Silver One", "CVE:SVE", "", "$0.42", "", "", "$0.60", "6000", "$2,520.00", "", "2.08%", "", "", "Silver"],
    ["", "CAD", "Capitan Silver Corp", "CVE:CAPT", "", "$1.94", "", "", "$2.13", "1250", "$2,425.00", "", "2.00%", "", "", "Silver"],
    ["", "CAD", "New Age Metals", "CVE:NAM", "", "$0.25", "", "", "$0.415", "9000", "$2,250.00", "", "1.85%", "", "", "Copper"],
    ["ADD!", "CAD", "Power Mining Corp", "MAXX", "", "$2.75", "", "", "$0.57", "700", "$1,925.00", "", "1.59%", "", "", "Hydro"],
    ["", "CAD", "Trinity One Metals", "CVE:TOM", "", "$0.19", "", "", "$0.248", "8000", "$1,520.00", "", "1.25%", "", "", "Silver"],
    ["", "AUD", "Atomic Eagle", "ASX:AEU", "", "$0.45", "", "", "$0.31", "2027", "$912.15", "", "0.76%", "", "", "Uranium"],
    ["ADD!", "CAD", "ENCORE energy", "CVE:EU", "", "$1.67", "", "", "$2.22", "325", "$542.75", "", "0.45%", "", "", "Uranium"],
    ["", "CAD", "Manhattan Uranium", "CVE:MANU", "", "$0.25", "", "", "$0.49", "2660", "$665.00", "", "0.55%", "", "", "Uranium"],
    ["", "USD", "BOSS ENERGY", "BQSSF", "", "$1.01", "", "", "$1.38", "500", "$505.00", "", "0.58%", "", "", "Uranium"],
    ["", "AUD", "Lotus UR ASX", "ASX:LOT", "", "$0.23", "", "", "$2.40", "956", "$219.88", "", "0.18%", "", "", "Uranium"],
    ["CCalls", "USD", "Sprott Uranium JR", "URNJ", "", "$24.42", "", "", "$29.55", "250", "$6,105.00", "", "6.98%", "", "", "Uranium"],
    ["CCalls", "USD", "Silver JR", "SILJ", "", "$29.86", "", "", "$30.53", "100", "$2,986.00", "", "2.42%", "", "", "Uranium"],
]


def sheet_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(SHEET_ROWS)
    return output.getvalue()


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class SheetAllocationTests(unittest.TestCase):
    @patch.object(generate.requests, "get", return_value=FakeResponse(sheet_csv()))
    def test_sector_allocation_comes_from_sheet_percentages(self, _request):
        _holdings, meta = generate.fetch_holdings_from_gsheet()

        self.assertEqual(meta["allocation_source"], "Google Sheet · % of Fund")
        self.assertEqual(
            meta["sector_allocations_pct"],
            [
                ("Graphene", 49.64),
                ("Uranium", 18.84),
                ("Gold", 12.41),
                ("Silver", 8.33),
                ("Copper", 6.94),
                ("Molybdenum", 2.27),
                ("Hydro", 1.59),
            ],
        )
        self.assertAlmostEqual(meta["sector_allocation_total_pct"], 100.02, places=2)

    def test_chart_is_scalable_glowing_and_displays_sheet_percentages(self):
        allocations = [
            ("Graphene", 49.64, ""),
            ("Uranium", 18.84, ""),
            ("Gold", 12.41, ""),
        ]

        chart = generate.build_donut(allocations)
        legend = generate.build_legend(allocations, 100.0)

        self.assertIn('viewBox="0 0 320 320"', chart)
        self.assertIn('data-allocation-source="google-sheet"', chart)
        self.assertIn('class="allocation-glow"', chart)
        self.assertIn('class="allocation-gloss"', chart)
        self.assertIn('id="allocation-gloss"', chart)
        self.assertIn("Portfolio allocation from Google Sheet", chart)
        self.assertNotIn('class="allocation-core-bolt"', chart)
        self.assertNotIn("&#x26A1;&#xFE0F;", chart)
        self.assertIn("#F5FF5A", chart)
        self.assertIn("#8CFF00", chart)
        self.assertIn("#63FF9B", chart)
        self.assertIn("#00E86F", chart)
        self.assertNotIn('style="width:120px;height:120px"', chart)
        self.assertIn("Graphene", legend)
        self.assertIn("49.6%", legend)
        self.assertIn("18.8%", legend)
        self.assertIn('data-allocation-sector="Graphene"', legend)

    def test_sheet_totals_survive_when_yfinance_is_unavailable(self):
        holdings = [{
            "ticker": "HG.CN",
            "display": "HG",
            "name": "Hydrograph",
            "shares": 9750,
            "currency": "CAD",
            "sector": "Graphene",
        }]
        meta = {
            "total_cad": 121390.06,
            "sector_allocations_pct": [("Graphene", 100.0)],
        }

        with patch.object(generate, "fetch_holdings_from_gsheet", return_value=(holdings, meta)):
            with patch.dict(sys.modules, {"yfinance": None}):
                result = generate.fetch_portfolio()

        self.assertEqual(result, ({}, holdings, meta))


if __name__ == "__main__":
    unittest.main()
