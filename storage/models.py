from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class RawDocument:
    source: str
    doc_type: str
    title: str
    content: str
    content_hash: str
    id: str = field(default_factory=lambda: str(uuid4()))
    url: str = ""
    publish_time: datetime | None = None
    fetched_at: datetime | None = None
    stock_code: str = ""
    stock_name: str = ""
    external_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawDocumentQuery:
    start_time: datetime | None = None
    end_time: datetime | None = None
    doc_type: str | None = None
    source: str | None = None
    limit: int = 100


@dataclass(frozen=True)
class DocumentChunk:
    raw_document_id: str
    chunk_index: int
    content: str
    content_hash: str
    id: str = field(default_factory=lambda: str(uuid4()))
    char_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding_status: str = "pending"


@dataclass(frozen=True)
class DocumentChunkQuery:
    raw_document_id: str | None = None
    embedding_status: str | None = None
    limit: int = 100


@dataclass(frozen=True)
class MarketSnapshot:
    trade_date: date
    code: str
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    open: float | None = None
    close: float | None = None
    high: float | None = None
    low: float | None = None
    pct_chg: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None
    limit_status: str = "none"
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketSnapshotQuery:
    trade_date: date | None = None
    code: str | None = None
    source: str | None = None
    instrument_type: str | None = None
    limit: int = 100


@dataclass(frozen=True)
class Observation:
    trade_date: date
    report_type: str
    theme: str
    hypothesis: str
    validation_condition: str
    invalid_condition: str
    priority: str
    id: str = field(default_factory=lambda: str(uuid4()))
    related_stocks: list[str] = field(default_factory=list)
    status: str = "pending"
    outcome: str = ""
    review_note: str = ""
    source_event_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ObservationQuery:
    start_date: date | None = None
    end_date: date | None = None
    trade_date: date | None = None
    report_type: str | None = None
    status: str | None = None
    limit: int = 100
