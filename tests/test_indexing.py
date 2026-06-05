from __future__ import annotations

import unittest

from analysis.indexing import build_chunks_for_document
from storage.models import RawDocument


class IndexingTests(unittest.TestCase):
    def test_build_chunks_for_document_carries_metadata(self) -> None:
        document = RawDocument(
            id="doc-1",
            source="notion",
            doc_type="note",
            title="交易复盘",
            content="第一段\n第二段",
            url="https://example.com",
            content_hash="raw-hash",
        )

        chunks = build_chunks_for_document(document, chunk_size=20, overlap=3)

        self.assertEqual(1, len(chunks))
        self.assertEqual("doc-1", chunks[0].raw_document_id)
        self.assertEqual(0, chunks[0].chunk_index)
        self.assertEqual("notion", chunks[0].metadata["source"])
        self.assertEqual("交易复盘", chunks[0].metadata["title"])
        self.assertEqual(64, len(chunks[0].content_hash))


if __name__ == "__main__":
    unittest.main()
