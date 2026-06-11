from __future__ import annotations

import io
import json
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from analysis.vector_index import QdrantClient, build_qdrant_point, search_knowledge, sync_vector_index
from app.config import Settings
from storage.models import DocumentChunk, DocumentChunkQuery


class FakeChunkRepository:
    def __init__(self, chunks):
        self.chunks = chunks
        self.updated = []

    def list(self, query):
        self.query = query
        return self.chunks

    def update_embedding_status(self, chunk_ids, status):
        self.updated.append((chunk_ids, status))
        return len(chunk_ids)


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.inputs = []

    def embed_texts(self, texts):
        self.inputs.append(texts)

        class Result:
            vectors = [[float(index), float(index + 1)] for index, _ in enumerate(texts)]

        return Result()


class FakeQdrantClient:
    def __init__(self) -> None:
        self.deleted = []
        self.upserted = []

    def delete_by_raw_document_id(self, raw_document_id):
        self.deleted.append(raw_document_id)

    def upsert_points(self, points):
        self.upserted.extend(points)

    def search(self, vector, limit):
        self.vector = vector
        self.limit = limit
        return []


class VectorIndexTests(unittest.TestCase):
    def test_qdrant_client_ensure_collection_sends_vector_config_and_api_key(self) -> None:
        captured = {}
        requests = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def read(self):
                return b"{}"

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            requests.append((request.full_url, request.get_method(), captured["payload"]))
            return FakeResponse()

        settings = Settings(
            qdrant_url="https://example.qdrant.io",
            qdrant_collection="market_knowledge",
            qdrant_api_key="secret",
        )

        with patch("analysis.vector_index.urlopen", side_effect=fake_urlopen):
            QdrantClient(settings).ensure_collection(1024)

        self.assertEqual("secret", captured["headers"]["Api-key"])
        self.assertEqual(
            [
                (
                    "https://example.qdrant.io/collections/market_knowledge",
                    "PUT",
                    {"vectors": {"size": 1024, "distance": "Cosine"}},
                ),
                (
                    "https://example.qdrant.io/collections/market_knowledge/index",
                    "PUT",
                    {"field_name": "raw_document_id", "field_schema": "keyword"},
                ),
            ],
            requests,
        )

    def test_qdrant_client_ensure_collection_rejects_missing_dimension(self) -> None:
        with self.assertRaises(ValueError):
            QdrantClient(Settings()).ensure_collection(0)

    def test_qdrant_client_ensure_collection_ignores_existing_collection_and_index(self) -> None:
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request.full_url, request.get_method(), timeout))
            raise HTTPError(
                request.full_url,
                409,
                "Conflict",
                hdrs=None,
                fp=io.BytesIO(b'{"status":{"error":"already exists"}}'),
            )

        settings = Settings(
            qdrant_url="https://example.qdrant.io",
            qdrant_collection="market_knowledge",
        )

        with patch("analysis.vector_index.urlopen", side_effect=fake_urlopen):
            QdrantClient(settings).ensure_collection(1024)

        self.assertEqual(
            [
                ("https://example.qdrant.io/collections/market_knowledge", "PUT", 30),
                ("https://example.qdrant.io/collections/market_knowledge/index", "PUT", 30),
            ],
            requests,
        )

    def test_build_qdrant_point_carries_chunk_payload(self) -> None:
        chunk = DocumentChunk(
            id="00000000-0000-0000-0000-000000000001",
            raw_document_id="doc-1",
            chunk_index=0,
            content="content",
            content_hash="hash",
            metadata={"source": "notion", "title": "title"},
        )

        point = build_qdrant_point(chunk, [0.1, 0.2])

        self.assertEqual(chunk.id, point["id"])
        self.assertEqual([0.1, 0.2], point["vector"])
        self.assertEqual("doc-1", point["payload"]["raw_document_id"])
        self.assertEqual("content", point["payload"]["content"])
        self.assertEqual("title", point["payload"]["title"])

    def test_sync_vector_index_replaces_vectors_per_document(self) -> None:
        chunks = [
            DocumentChunk(
                id="00000000-0000-0000-0000-000000000001",
                raw_document_id="doc-1",
                chunk_index=0,
                content="first",
                content_hash="hash-1",
            ),
            DocumentChunk(
                id="00000000-0000-0000-0000-000000000002",
                raw_document_id="doc-1",
                chunk_index=1,
                content="second",
                content_hash="hash-2",
            ),
        ]
        chunk_repository = FakeChunkRepository(chunks)
        embedding_client = FakeEmbeddingClient()
        qdrant_client = FakeQdrantClient()

        result = sync_vector_index(
            chunk_repository,
            embedding_client,
            qdrant_client,
            DocumentChunkQuery(embedding_status="pending", limit=10),
        )

        self.assertEqual(2, result.chunk_count)
        self.assertEqual(1, result.document_count)
        self.assertEqual(["doc-1"], qdrant_client.deleted)
        self.assertEqual(["first", "second"], embedding_client.inputs[0])
        self.assertEqual(2, len(qdrant_client.upserted))
        self.assertEqual([(["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"], "embedded")], chunk_repository.updated)

    def test_search_knowledge_embeds_query_then_searches(self) -> None:
        embedding_client = FakeEmbeddingClient()
        qdrant_client = FakeQdrantClient()

        matches = search_knowledge(embedding_client, qdrant_client, "query", limit=3)

        self.assertEqual([], matches)
        self.assertEqual(["query"], embedding_client.inputs[0])
        self.assertEqual([0.0, 1.0], qdrant_client.vector)
        self.assertEqual(3, qdrant_client.limit)


if __name__ == "__main__":
    unittest.main()
