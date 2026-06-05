from __future__ import annotations

from dataclasses import dataclass

from parsers.chunking import split_text
from storage.models import DocumentChunk, RawDocument, RawDocumentQuery
from storage.repositories import (
    DocumentChunkRepository,
    RawDocumentRepository,
    build_chunk_hash,
)


@dataclass(frozen=True)
class BuildIndexResult:
    document_count: int
    chunk_count: int


def build_chunks_for_document(document: RawDocument, chunk_size: int, overlap: int) -> list[DocumentChunk]:
    chunks = split_text(document.content, chunk_size=chunk_size, overlap=overlap)
    return [
        DocumentChunk(
            raw_document_id=document.id,
            chunk_index=index,
            content=content,
            char_count=len(content),
            metadata={
                "source": document.source,
                "doc_type": document.doc_type,
                "title": document.title,
                "url": document.url,
            },
            content_hash=build_chunk_hash(document.id, index, content),
        )
        for index, content in enumerate(chunks)
    ]


def build_local_index(
    raw_repository: RawDocumentRepository,
    chunk_repository: DocumentChunkRepository,
    query: RawDocumentQuery,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> BuildIndexResult:
    documents = raw_repository.list(query)
    chunk_count = 0
    for document in documents:
        chunks = build_chunks_for_document(document, chunk_size=chunk_size, overlap=overlap)
        chunk_count += chunk_repository.replace_for_document(document.id, chunks)
    return BuildIndexResult(document_count=len(documents), chunk_count=chunk_count)
