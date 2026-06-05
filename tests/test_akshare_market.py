from __future__ import annotations

import unittest
from datetime import date

from collectors.akshare_market import (
    akshare_index_row_to_market_snapshot,
    akshare_row_to_market_snapshot,
    collect_stock_daily_range,
    normalize_index_code,
    normalize_prefixed_stock_code,
    normalize_stock_code,
)


class AkshareMarketTests(unittest.TestCase):
    def test_normalize_stock_code(self) -> None:
        self.assertEqual("000001", normalize_stock_code("000001.SZ"))
        self.assertEqual("600000", normalize_stock_code("600000.sh"))

    def test_normalize_prefixed_stock_code(self) -> None:
        self.assertEqual("sz000001", normalize_prefixed_stock_code("000001"))
        self.assertEqual("sh600000", normalize_prefixed_stock_code("600000"))

    def test_normalize_index_code(self) -> None:
        self.assertEqual("sh000001", normalize_index_code("000001.SH"))
        self.assertEqual("sz399001", normalize_index_code("sz399001"))
        self.assertEqual("sz399006", normalize_index_code("399006"))

    def test_akshare_row_to_market_snapshot(self) -> None:
        snapshot = akshare_row_to_market_snapshot(
            {
                "日期": "2024-05-28",
                "股票代码": "000001",
                "开盘": 10.1,
                "收盘": 10.2,
                "最高": 10.5,
                "最低": 10.0,
                "成交额": 123456.7,
                "涨跌幅": 1.23,
                "换手率": 0.45,
                "成交量": 1000,
                "振幅": 2.0,
                "涨跌额": 0.12,
            },
            fallback_code="000001",
        )

        self.assertEqual(date(2024, 5, 28), snapshot.trade_date)
        self.assertEqual("000001", snapshot.code)
        self.assertEqual(10.2, snapshot.close)
        self.assertEqual(1.23, snapshot.pct_chg)
        self.assertEqual("akshare", snapshot.source)
        self.assertEqual(1000.0, snapshot.metadata["volume"])
        self.assertEqual("stock", snapshot.metadata["instrument_type"])
        self.assertEqual("eastmoney", snapshot.metadata["data_provider"])

    def test_akshare_index_row_to_market_snapshot(self) -> None:
        snapshot = akshare_index_row_to_market_snapshot(
            {
                "date": "2024-05-28",
                "open": 3100.1,
                "close": 3120.2,
                "high": 3130.5,
                "low": 3090.0,
                "volume": 123456,
                "amount": 987654321,
            },
            fallback_code="000001.SH",
        )

        self.assertEqual(date(2024, 5, 28), snapshot.trade_date)
        self.assertEqual("sh000001", snapshot.code)
        self.assertEqual(3120.2, snapshot.close)
        self.assertEqual("akshare_index", snapshot.source)
        self.assertEqual("index", snapshot.metadata["instrument_type"])
        self.assertEqual("akshare.stock_zh_index_daily", snapshot.metadata["data_provider"])
        self.assertEqual(123456.0, snapshot.metadata["volume"])

    def test_collect_stock_daily_range_falls_back_to_daily_api(self) -> None:
        class FakeFrame:
            empty = False

            def to_dict(self, orient: str):
                if orient != "records":
                    raise AssertionError(orient)
                return [
                    {
                        "date": "2024-05-28",
                        "open": 10.1,
                        "high": 10.5,
                        "low": 10.0,
                        "close": 10.2,
                        "volume": 1000,
                        "amount": 123456.7,
                    }
                ]

        calls = {}

        class FakeAkshare:
            def stock_zh_a_hist(self, **kwargs):
                raise ConnectionError("eastmoney closed")

            def stock_zh_a_daily(self, **kwargs):
                calls.update(kwargs)
                return FakeFrame()

        from unittest.mock import patch

        with patch("collectors.akshare_market.import_akshare", return_value=FakeAkshare()):
            snapshots = collect_stock_daily_range("000001", date(2024, 5, 27), date(2024, 5, 28))

        self.assertEqual(1, len(snapshots))
        self.assertEqual("sz000001", calls["symbol"])
        self.assertEqual("20240527", calls["start_date"])
        self.assertEqual("20240528", calls["end_date"])
        self.assertEqual("000001", snapshots[0].code)
        self.assertEqual(10.2, snapshots[0].close)
        self.assertEqual("sina", snapshots[0].metadata["data_provider"])
        self.assertEqual(1000.0, snapshots[0].metadata["volume"])


if __name__ == "__main__":
    unittest.main()
