from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.config import Settings


class EmbeddingError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingResult:
    text_count: int
    vectors: list[list[float]]


class EmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        if settings.embedding_provider != "openai-compatible":
            raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider}")
        if not settings.embedding_api_key:
            raise ValueError("EMBEDDING_API_KEY or OPENAI_API_KEY is required.")
        if not settings.embedding_model:
            raise ValueError("EMBEDDING_MODEL is required.")
        self.settings = settings

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        payload = build_embeddings_payload(self.settings.embedding_model, texts)
        response = post_embeddings(
            base_url=self.settings.embedding_base_url,
            api_key=self.settings.embedding_api_key,
            payload=payload,
            timeout=self.settings.embedding_timeout,
        )
        vectors = parse_embedding_vectors(response)
        return EmbeddingResult(text_count=len(texts), vectors=vectors)


def build_embeddings_payload(model: str, texts: list[str]) -> dict[str, Any]:
    return {"model": model, "input": texts}


def post_embeddings(base_url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = Request(
        f"{base_url.rstrip('/')}/embeddings",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise EmbeddingError(f"Embedding request failed: {exc.code} {message}") from exc


def parse_embedding_vectors(response: dict[str, Any]) -> list[list[float]]:
    try:
        return [item["embedding"] for item in sorted(response["data"], key=lambda item: item["index"])]
    except (KeyError, TypeError) as exc:
        raise EmbeddingError("Embedding response did not contain sortable data[].embedding values.") from exc
