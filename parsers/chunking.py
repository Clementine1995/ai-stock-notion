from __future__ import annotations


def split_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0.")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")

    normalized = normalize_text(text)
    if not normalized:
        return []

    paragraphs = [paragraph.strip() for paragraph in normalized.split("\n") if paragraph.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(split_long_paragraph(paragraph, chunk_size, overlap))
            continue

        candidate = paragraph if not current else f"{current}\n{paragraph}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        chunks.append(current)
        current = with_overlap(current, overlap, paragraph)

    if current:
        chunks.append(current)
    return chunks


def normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def split_long_paragraph(paragraph: str, chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(start + chunk_size, len(paragraph))
        chunks.append(paragraph[start:end])
        if end == len(paragraph):
            break
        start = end - overlap
    return chunks


def with_overlap(previous: str, overlap: int, next_paragraph: str) -> str:
    if overlap == 0:
        return next_paragraph
    tail = previous[-overlap:].strip()
    if not tail:
        return next_paragraph
    return f"{tail}\n{next_paragraph}"
