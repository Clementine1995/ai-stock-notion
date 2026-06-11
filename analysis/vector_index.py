from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.config import Settings
from storage.models import DocumentChunk, DocumentChunkQuery
from storage.repositories import DocumentChunkRepository


class VectorIndexError(RuntimeError):
    pass


@dataclass(frozen=True)
class VectorSyncResult:
    chunk_count: int
    document_count: int


@dataclass(frozen=True)
class KnowledgeMatch:
    score: float
    content: str
    metadata: dict[str, Any]


class QdrantClient:
    def __init__(self, settings: Settings) -> None:
        self.url = settings.qdrant_url.rstrip("/")
        self.collection = settings.qdrant_collection
        self.api_key = settings.qdrant_api_key

    def ensure_collection(self, vector_size: int, distance: str = "Cosine") -> None:
        if vector_size <= 0:
            raise ValueError("EMBEDDING_DIMENSION must be greater than 0 to create a Qdrant collection.")
        payload = {"vectors": {"size": vector_size, "distance": distance}}
        self._request("PUT", f"/collections/{self.collection}", payload, ignored_statuses={409})
        self.ensure_payload_index("raw_document_id", "keyword")

    def ensure_payload_index(self, field_name: str, field_schema: str) -> None:
        payload = {"field_name": field_name, "field_schema": field_schema}
        self._request("PUT", f"/collections/{self.collection}/index", payload, ignored_statuses={409})

    def delete_by_raw_document_id(self, raw_document_id: str) -> None:
        payload = {
            "filter": {
                "must": [
                    {"key": "raw_document_id", "match": {"value": raw_document_id}},
                ]
            }
        }
        self._request("POST", f"/collections/{self.collection}/points/delete", payload)

    def upsert_points(self, points: list[dict[str, Any]]) -> None:
        if not points:
            return
        self._request("PUT", f"/collections/{self.collection}/points", {"points": points})

    def search(self, vector: list[float], limit: int) -> list[KnowledgeMatch]:
        response = self._request(
            "POST",
            f"/collections/{self.collection}/points/search",
            {"vector": vector, "limit": limit, "with_payload": True},
        )
        return [
            KnowledgeMatch(
                score=float(item.get("score", 0)),
                content=item.get("payload", {}).get("content", ""),
                metadata={key: value for key, value in item.get("payload", {}).items() if key != "content"},
            )
            for item in response.get("result", [])
        ]

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        ignored_statuses: set[int] | None = None,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        request = Request(
            f"{self.url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except HTTPError as exc:
            if ignored_statuses and exc.code in ignored_statuses:
                return {}
            message = exc.read().decode("utf-8", errors="replace")
            raise VectorIndexError(f"Qdrant request failed: {exc.code} {message}") from exc


def sync_vector_index(
    chunk_repository: DocumentChunkRepository,
    embedding_client: Any,
    qdrant_client: Any,
    query: DocumentChunkQuery,
) -> VectorSyncResult:
    chunks = chunk_repository.list(query)
    chunks_by_document = group_chunks_by_document(chunks)
    for raw_document_id, document_chunks in chunks_by_document.items():
        qdrant_client.delete_by_raw_document_id(raw_document_id)
        vectors = embedding_client.embed_texts([chunk.content for chunk in document_chunks]).vectors
        points = [build_qdrant_point(chunk, vector) for chunk, vector in zip(document_chunks, vectors, strict=True)]
        qdrant_client.upsert_points(points)
        chunk_repository.update_embedding_status([chunk.id for chunk in document_chunks], "embedded")
    return VectorSyncResult(chunk_count=len(chunks), document_count=len(chunks_by_document))


def search_knowledge(embedding_client: Any, qdrant_client: Any, query: str, limit: int) -> list[KnowledgeMatch]:
    vector = embedding_client.embed_texts([query]).vectors[0]
    return qdrant_client.search(vector, limit=limit)


def group_chunks_by_document(chunks: list[DocumentChunk]) -> dict[str, list[DocumentChunk]]:
    grouped: dict[str, list[DocumentChunk]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.raw_document_id, []).append(chunk)
    return grouped


def build_qdrant_point(chunk: DocumentChunk, vector: list[float]) -> dict[str, Any]:
    payload = {
        **chunk.metadata,
        "raw_document_id": chunk.raw_document_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "content_hash": chunk.content_hash,
    }
    return {"id": chunk.id, "vector": vector, "payload": payload}
