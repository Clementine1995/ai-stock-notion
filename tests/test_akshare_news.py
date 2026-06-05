from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from collectors.akshare_news import (
    akshare_cctv_news_row_to_raw_document,
    akshare_stock_news_row_to_raw_document,
    collect_cctv_news,
    collect_stock_news,
    normalize_text,
)


class AkshareNewsTests(unittest.TestCase):
    def test_akshare_cctv_news_row_to_raw_document(self) -> None:
        document = akshare_cctv_news_row_to_raw_document(
            {
                "date": "20240528",
                "title": "新闻联播标题",
                "content": "央视网消息  产业政策更新",
            }
        )

        self.assertEqual("akshare_cctv", document.source)
        self.assertEqual("news", document.doc_type)
        self.assertEqual("新闻联播标题", document.title)
        self.assertEqual("央视网消息 产业政策更新", document.content)
        self.assertEqual(date(2024, 5, 28), document.publish_time.date())
        self.assertTrue(document.external_id.startswith("news:cctv:"))
        self.assertEqual("cctv", document.metadata["news_source"])
        self.assertEqual("akshare.news_cctv", document.metadata["data_provider"])
        self.assertEqual("daily_digest", document.metadata["freshness_tier"])
        self.assertEqual(64, len(document.content_hash))

    def test_akshare_stock_news_row_to_raw_document(self) -> None:
        document = akshare_stock_news_row_to_raw_document(
            {
                "关键词": "000001",
                "新闻标题": "平安银行盘中异动",
                "新闻内容": "平安银行成交额放大。",
                "发布时间": "2026-06-05 10:31:00",
                "文章来源": "东方财富",
                "新闻链接": "http://finance.eastmoney.com/a/test.html",
            },
            fallback_stock_code="000001",
        )

        self.assertEqual("akshare_eastmoney", document.source)
        self.assertEqual("news", document.doc_type)
        self.assertEqual("000001", document.stock_code)
        self.assertEqual("平安银行盘中异动", document.title)
        self.assertEqual("http://finance.eastmoney.com/a/test.html", document.url)
        self.assertEqual("东方财富", document.metadata["media"])
        self.assertEqual("recent_stock_news", document.metadata["freshness_tier"])
        self.assertEqual("akshare.stock_news_em", document.metadata["data_provider"])
        self.assertEqual("2026-06-05T10:31:00", document.publish_time.isoformat())

    def test_collect_cctv_news_calls_akshare_by_date(self) -> None:
        class FakeFrame:
            empty = False

            def to_dict(self, orient: str):
                if orient != "records":
                    raise AssertionError(orient)
                return [{"date": "20240528", "title": "标题", "content": "正文"}]

        calls = {}

        class FakeAkshare:
            def news_cctv(self, **kwargs):
                calls.update(kwargs)
                return FakeFrame()

        with patch("collectors.akshare_news.import_akshare", return_value=FakeAkshare()):
            documents = collect_cctv_news(date(2024, 5, 28))

        self.assertEqual(1, len(documents))
        self.assertEqual("20240528", calls["date"])

    def test_collect_stock_news_filters_by_min_publish_date(self) -> None:
        class FakeFrame:
            empty = False

            def to_dict(self, orient: str):
                if orient != "records":
                    raise AssertionError(orient)
                return [
                    {
                        "关键词": "000001",
                        "新闻标题": "旧新闻",
                        "新闻内容": "旧内容",
                        "发布时间": "2026-06-04 15:00:00",
                        "文章来源": "东方财富",
                        "新闻链接": "http://finance.eastmoney.com/a/old.html",
                    },
                    {
                        "关键词": "000001",
                        "新闻标题": "今日新闻",
                        "新闻内容": "今日内容",
                        "发布时间": "2026-06-05 09:31:00",
                        "文章来源": "东方财富",
                        "新闻链接": "http://finance.eastmoney.com/a/new.html",
                    },
                ]

        calls = {}

        class FakeAkshare:
            def stock_news_em(self, **kwargs):
                calls.update(kwargs)
                return FakeFrame()

        with patch("collectors.akshare_news.import_akshare", return_value=FakeAkshare()):
            documents = collect_stock_news(["000001"], min_publish_date=date(2026, 6, 5))

        self.assertEqual("000001", calls["symbol"])
        self.assertEqual(["今日新闻"], [document.title for document in documents])

    def test_normalize_text_collapses_whitespace(self) -> None:
        self.assertEqual("a b c", normalize_text(" a\n b\tc "))


if __name__ == "__main__":
    unittest.main()
