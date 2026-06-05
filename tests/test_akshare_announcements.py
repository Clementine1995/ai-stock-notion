from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from collectors.akshare_announcements import akshare_announcement_row_to_raw_document, collect_announcements


class AkshareAnnouncementTests(unittest.TestCase):
    def test_akshare_announcement_row_to_raw_document(self) -> None:
        document = akshare_announcement_row_to_raw_document(
            {
                "代码": "000001",
                "名称": "平安银行",
                "公告标题": "平安银行股份有限公司年度报告",
                "公告类型": "财务报告",
                "公告日期": date(2024, 5, 28),
                "网址": "https://data.eastmoney.com/notices/detail/000001/test.html",
            }
        )

        self.assertEqual("akshare", document.source)
        self.assertEqual("announcement", document.doc_type)
        self.assertEqual("000001", document.stock_code)
        self.assertEqual("平安银行", document.stock_name)
        self.assertEqual(date(2024, 5, 28), document.publish_time.date())
        self.assertEqual("announcement:https://data.eastmoney.com/notices/detail/000001/test.html", document.external_id)
        self.assertEqual("财务报告", document.metadata["announcement_category"])
        self.assertEqual("eastmoney.stock_notice_report", document.metadata["data_provider"])
        self.assertIn("Title: 平安银行股份有限公司年度报告", document.content)

    def test_collect_announcements_calls_akshare_by_date_and_category(self) -> None:
        class FakeFrame:
            empty = False

            def to_dict(self, orient: str):
                if orient != "records":
                    raise AssertionError(orient)
                return [
                    {
                        "代码": "000001",
                        "名称": "平安银行",
                        "公告标题": "平安银行股份有限公司年度报告",
                        "公告类型": "财务报告",
                        "公告日期": "2024-05-28",
                        "网址": "https://data.eastmoney.com/notices/detail/000001/test.html",
                    }
                ]

        calls = {}

        class FakeAkshare:
            def stock_notice_report(self, **kwargs):
                calls.update(kwargs)
                return FakeFrame()

        with patch("collectors.akshare_announcements.import_akshare", return_value=FakeAkshare()):
            documents = collect_announcements(date(2024, 5, 28), category="财务报告")

        self.assertEqual(1, len(documents))
        self.assertEqual("财务报告", calls["symbol"])
        self.assertEqual("20240528", calls["date"])

    def test_announcement_hash_includes_url(self) -> None:
        base_row = {
            "代码": "000001",
            "名称": "平安银行",
            "公告标题": "平安银行股份有限公司年度报告",
            "公告类型": "财务报告",
            "公告日期": date(2024, 5, 28),
        }

        first = akshare_announcement_row_to_raw_document({**base_row, "网址": "https://example.com/1.html"})
        second = akshare_announcement_row_to_raw_document({**base_row, "网址": "https://example.com/2.html"})

        self.assertNotEqual(first.content_hash, second.content_hash)


if __name__ == "__main__":
    unittest.main()
