import os
import unittest
from unittest.mock import Mock, patch

import generate


class AlpacaFallbackTests(unittest.TestCase):
    def test_public_summary_preserves_novairecito_account_without_local_credentials(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "ok": True,
            "equity": 542.85,
            "inceptionRoi": 8.57,
            "positions": [
                {
                    "symbol": "URNJ",
                    "marketValue": 208.8,
                    "pctPnl": -11.641,
                    "portfolioWeight": 38.4658,
                }
            ],
        }
        empty_credentials = {
            "ALPACA_API_KEY": "",
            "APCA_API_KEY_ID": "",
            "ALPACA_SECRET_KEY": "",
            "APCA_API_SECRET_KEY": "",
        }
        with patch.dict(os.environ, empty_credentials, clear=False), patch.object(
            generate.requests, "get", return_value=response
        ) as get:
            account = generate.fetch_alpaca()

        self.assertTrue(account["funded"])
        self.assertEqual(account["equity"], 542.85)
        self.assertEqual(account["positions"][0]["symbol"], "URNJ")
        self.assertAlmostEqual(account["positions"][0]["portfolio_weight"], 38.4658)
        get.assert_called_once_with(
            "https://novairesignal.com/api/alpaca-summary",
            headers={"User-Agent": "NovaireSignalGenerator/1.0"},
            timeout=15,
        )


if __name__ == "__main__":
    unittest.main()
