from __future__ import annotations

import unittest

from analysis.embeddings import EmbeddingClient, EmbeddingError, build_embeddings_payload, parse_embedding_vectors
from app.config import Settings


class EmbeddingTests(unittest.TestCase):
    def test_build_embeddings_payload(self) -> None:
        payload = build_embeddings_payload("embedding-model", ["a", "b"])

        self.assertEqual({"model": "embedding-model", "input": ["a", "b"]}, payload)

    def test_parse_embedding_vectors_sorts_by_index(self) -> None:
        vectors = parse_embedding_vectors(
            {
                "data": [
                    {"index": 1, "embedding": [0.2, 0.3]},
                    {"index": 0, "embedding": [0.0, 0.1]},
                ]
            }
        )

        self.assertEqual([[0.0, 0.1], [0.2, 0.3]], vectors)

    def test_parse_embedding_vectors_rejects_invalid_response(self) -> None:
        with self.assertRaises(EmbeddingError):
            parse_embedding_vectors({"data": [{"embedding": [0.1]}]})

    def test_embedding_client_rejects_unknown_provider(self) -> None:
        settings = Settings(
            embedding_provider="dashscope",
            embedding_api_key="key",
            embedding_model="model",
        )

        with self.assertRaises(ValueError):
            EmbeddingClient(settings)


if __name__ == "__main__":
    unittest.main()
