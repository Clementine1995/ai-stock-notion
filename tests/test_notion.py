from __future__ import annotations

import unittest

from collectors.notion import (
    NotionPageContent,
    extract_block_text,
    extract_page_title,
    page_content_to_raw_document,
    rich_text_to_plain_text,
    split_notion_page_ids,
)


class NotionParserTests(unittest.TestCase):
    def test_rich_text_to_plain_text(self) -> None:
        self.assertEqual(
            "高位利好兑现",
            rich_text_to_plain_text([{"plain_text": "高位"}, {"plain_text": "利好兑现"}]),
        )

    def test_extract_block_text_from_paragraph(self) -> None:
        block = {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": "观察成交量是否放大"}]},
        }

        self.assertEqual("观察成交量是否放大", extract_block_text(block))

    def test_extract_page_title(self) -> None:
        page = {
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "交易复盘"}],
                }
            }
        }

        self.assertEqual("交易复盘", extract_page_title(page))

    def test_split_notion_page_ids_accepts_urls(self) -> None:
        page_ids = split_notion_page_ids(
            "https://www.notion.so/workspace/Test-1234567890abcdef1234567890abcdef,abcdef"
        )

        self.assertEqual(["1234567890abcdef1234567890abcdef", "abcdef"], page_ids)

    def test_page_content_to_raw_document(self) -> None:
        document = page_content_to_raw_document(
            NotionPageContent(
                page_id="page-id",
                title="交易复盘",
                content="只记录事实。",
                url="https://notion.so/page-id",
                last_edited_time=None,
            )
        )

        self.assertEqual("notion", document.source)
        self.assertEqual("note", document.doc_type)
        self.assertEqual("page-id", document.external_id)
        self.assertEqual({"page_id": "page-id"}, document.metadata)
        self.assertEqual(64, len(document.content_hash))


if __name__ == "__main__":
    unittest.main()
