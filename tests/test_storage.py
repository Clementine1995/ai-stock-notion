from __future__ import annotations

import unittest
from datetime import UTC, datetime

from storage.models import MarketSnapshot, MarketSnapshotQuery, RawDocument
from storage.repositories import (
    DocumentChunkRepository,
    MarketSnapshotRepository,
    RawDocumentRepository,
    build_chunk_hash,
    build_content_hash,
)


class FakeCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.params = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, sql, params) -> None:
        self.sql = sql
        self.params = params

    def executemany(self, sql, params_seq) -> None:
        self.sql = sql
        self.params = list(params_seq)

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self) -> None:
        self.last_cursor = FakeCursor()
        self.commit_count = 0

    def cursor(self):
        return self.last_cursor

    def commit(self) -> None:
        self.commit_count += 1


class StorageModelTests(unittest.TestCase):
    def test_build_content_hash_is_stable(self) -> None:
        publish_time = datetime(2026, 5, 29, 9, 30, tzinfo=UTC)

        first = build_content_hash("notion", "交易规则", publish_time, "000001.SZ")
        second = build_content_hash("notion", "交易规则", publish_time, "000001.SZ")

        self.assertEqual(first, second)
        self.assertEqual(64, len(first))

    def test_build_chunk_hash_is_stable(self) -> None:
        first = build_chunk_hash("doc-id", 0, "content")
        second = build_chunk_hash("doc-id", 0, "content")

        self.assertEqual(first, second)
        self.assertEqual(64, len(first))

    def test_raw_document_defaults_are_safe(self) -> None:
        document = RawDocument(
            source="notion",
            doc_type="note",
            title="交易规则",
            content="只记录事实和条件。",
            content_hash="hash",
        )

        self.assertEqual("", document.url)
        self.assertEqual("", document.external_id)
        self.assertEqual({}, document.metadata)
        self.assertTrue(document.id)

    def test_market_snapshot_defaults_are_safe(self) -> None:
        snapshot = MarketSnapshot(trade_date=datetime(2026, 5, 29, tzinfo=UTC).date(), code="000001")

        self.assertEqual("none", snapshot.limit_status)
        self.assertEqual({}, snapshot.metadata)
        self.assertTrue(snapshot.id)

    def test_market_snapshot_query_does_not_filter_instrument_by_default(self) -> None:
        query = MarketSnapshotQuery()

        self.assertIsNone(query.instrument_type)

    def test_raw_document_list_ignores_market_instrument_filter(self) -> None:
        connection = FakeConnection()

        documents = RawDocumentRepository(connection).list()

        self.assertEqual([], documents)
        self.assertNotIn("instrument_type", connection.last_cursor.sql)

    def test_market_snapshot_list_filters_by_instrument_type(self) -> None:
        connection = FakeConnection()
        query = MarketSnapshotQuery(instrument_type="stock")

        snapshots = MarketSnapshotRepository(connection).list(query)

        self.assertEqual([], snapshots)
        self.assertIn("metadata->>'instrument_type' = %(instrument_type)s", connection.last_cursor.sql)
        self.assertEqual("stock", connection.last_cursor.params["instrument_type"])

    def test_raw_document_upsert_many_commits_once(self) -> None:
        connection = FakeConnection()
        document = RawDocument(
            source="akshare",
            doc_type="announcement",
            title="title",
            content="content",
            content_hash="hash",
            external_id="announcement:url",
        )

        count = RawDocumentRepository(connection).upsert_many([document])

        self.assertEqual(1, count)
        self.assertEqual(1, connection.commit_count)
        self.assertIn("ON CONFLICT (source, external_id)", connection.last_cursor.sql)
        self.assertEqual("announcement:url", connection.last_cursor.params[0]["external_id"])

    def test_document_chunk_update_embedding_status(self) -> None:
        connection = FakeConnection()

        count = DocumentChunkRepository(connection).update_embedding_status(["chunk-1"], "embedded")

        self.assertEqual(1, count)
        self.assertEqual(1, connection.commit_count)
        self.assertIn("UPDATE document_chunks", connection.last_cursor.sql)
        self.assertEqual("embedded", connection.last_cursor.params["status"])
        self.assertEqual(["chunk-1"], connection.last_cursor.params["chunk_ids"])


if __name__ == "__main__":
    unittest.main()
