from __future__ import annotations

import unittest
from argparse import Namespace
from datetime import date
from unittest.mock import patch

from app.config import Settings
from app.main import resolve_market_codes, resolve_market_date_range, split_codes, without_http_proxy


class MarketCliTests(unittest.TestCase):
    def test_split_codes_accepts_common_separators(self) -> None:
        self.assertEqual(["000001", "600000", "sh000001"], split_codes("000001,600000 sh000001"))

    def test_resolve_market_codes_uses_default_stock_when_empty(self) -> None:
        args = Namespace(stock_code=None, index_code=None)

        stock_codes, index_codes = resolve_market_codes(args, Settings())

        self.assertEqual(["000001"], stock_codes)
        self.assertEqual([], index_codes)

    def test_resolve_market_codes_uses_configured_batches(self) -> None:
        args = Namespace(stock_code=None, index_code=None)
        settings = Settings(market_stock_codes="000001,600000", market_index_codes="sh000001,sz399001")

        stock_codes, index_codes = resolve_market_codes(args, settings)

        self.assertEqual(["000001", "600000"], stock_codes)
        self.assertEqual(["sh000001", "sz399001"], index_codes)

    def test_resolve_market_codes_lets_cli_override_config(self) -> None:
        args = Namespace(stock_code=["000002", "000002"], index_code=["sh000001"])
        settings = Settings(market_stock_codes="000001,600000", market_index_codes="sz399001")

        stock_codes, index_codes = resolve_market_codes(args, settings)

        self.assertEqual(["000002"], stock_codes)
        self.assertEqual(["sh000001"], index_codes)

    def test_resolve_market_date_range_accepts_start_and_end(self) -> None:
        args = Namespace(date=None, start_date="2024-05-27", end_date="2024-05-28")

        start_date, end_date = resolve_market_date_range(args)

        self.assertEqual(date(2024, 5, 27), start_date)
        self.assertEqual(date(2024, 5, 28), end_date)

    def test_resolve_market_date_range_rejects_mixed_date_args(self) -> None:
        args = Namespace(date="2024-05-28", start_date="2024-05-27", end_date=None)

        with self.assertRaises(ValueError):
            resolve_market_date_range(args)

    def test_without_http_proxy_restores_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "HTTPS_PROXY": "http://127.0.0.1:7890",
                "ALL_PROXY": "socks5://127.0.0.1:7891",
            },
            clear=True,
        ):
            with without_http_proxy(enabled=True):
                import os

                self.assertNotIn("HTTPS_PROXY", os.environ)
                self.assertNotIn("ALL_PROXY", os.environ)
                self.assertEqual("*", os.environ["NO_PROXY"])

            import os

            self.assertEqual("http://127.0.0.1:7890", os.environ["HTTPS_PROXY"])
            self.assertEqual("socks5://127.0.0.1:7891", os.environ["ALL_PROXY"])
            self.assertNotIn("NO_PROXY", os.environ)


if __name__ == "__main__":
    unittest.main()
