from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from storage.models import (
    DocumentChunk,
    DocumentChunkQuery,
    MarketSnapshot,
    MarketSnapshotQuery,
    Observation,
    ObservationQuery,
    RawDocument,
    RawDocumentQuery,
)


def build_content_hash(source: str, title: str, publish_time: datetime | None, stock_code: str = "") -> str:
    publish_value = publish_time.isoformat() if publish_time else ""
    raw_value = "|".join((source.strip(), title.strip(), publish_value, stock_code.strip()))
    return sha256(raw_value.encode("utf-8")).hexdigest()


def build_chunk_hash(raw_document_id: str, chunk_index: int, content: str) -> str:
    raw_value = "|".join((raw_document_id, str(chunk_index), content))
    return sha256(raw_value.encode("utf-8")).hexdigest()


def build_observation_id(trade_date: object, report_type: str, theme: str, source_event_ids: list[str]) -> str:
    raw_value = "|".join((str(trade_date), report_type.strip(), theme.strip(), ",".join(sorted(source_event_ids))))
    return sha256(raw_value.encode("utf-8")).hexdigest()


def raw_document_conflict_sql(document: RawDocument) -> str:
    return (
        "ON CONFLICT (source, external_id) WHERE external_id <> '' DO UPDATE SET"
        if document.external_id
        else "ON CONFLICT (content_hash) DO UPDATE SET"
    )


def raw_document_params(document: RawDocument, jsonb_factory: Any, fetched_at: datetime) -> dict[str, object]:
    return {
        "id": document.id,
        "source": document.source,
        "doc_type": document.doc_type,
        "title": document.title,
        "content": document.content,
        "url": document.url,
        "publish_time": document.publish_time,
        "fetched_at": document.fetched_at or fetched_at,
        "stock_code": document.stock_code,
        "stock_name": document.stock_name,
        "external_id": document.external_id,
        "metadata": jsonb_factory(document.metadata),
        "content_hash": document.content_hash,
    }


class RawDocumentRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def upsert(self, document: RawDocument) -> RawDocument:
        from psycopg.types.json import Jsonb

        fetched_at = document.fetched_at or datetime.now(UTC)
        conflict_sql = raw_document_conflict_sql(document)
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO raw_documents (
                    id, source, doc_type, title, content, url, publish_time,
                    fetched_at, stock_code, stock_name, external_id, metadata, content_hash
                )
                VALUES (
                    %(id)s, %(source)s, %(doc_type)s, %(title)s, %(content)s, %(url)s,
                    %(publish_time)s, %(fetched_at)s, %(stock_code)s, %(stock_name)s,
                    %(external_id)s, %(metadata)s, %(content_hash)s
                )
                {conflict_sql}
                    source = EXCLUDED.source,
                    doc_type = EXCLUDED.doc_type,
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    url = EXCLUDED.url,
                    publish_time = EXCLUDED.publish_time,
                    fetched_at = EXCLUDED.fetched_at,
                    stock_code = EXCLUDED.stock_code,
                    stock_name = EXCLUDED.stock_name,
                    external_id = EXCLUDED.external_id,
                    metadata = EXCLUDED.metadata,
                    content_hash = EXCLUDED.content_hash,
                    updated_at = NOW()
                RETURNING id, fetched_at
                """,
                raw_document_params(document, Jsonb, fetched_at),
            )
            row = cursor.fetchone()
        self.connection.commit()
        return RawDocument(
            id=row[0],
            source=document.source,
            doc_type=document.doc_type,
            title=document.title,
            content=document.content,
            url=document.url,
            publish_time=document.publish_time,
            fetched_at=row[1],
            stock_code=document.stock_code,
            stock_name=document.stock_name,
            external_id=document.external_id,
            metadata=document.metadata,
            content_hash=document.content_hash,
        )

    def upsert_many(self, documents: list[RawDocument]) -> int:
        from psycopg.types.json import Jsonb

        fetched_at = datetime.now(UTC)
        with self.connection.cursor() as cursor:
            grouped_documents: dict[str, list[RawDocument]] = {}
            for document in documents:
                grouped_documents.setdefault(raw_document_conflict_sql(document), []).append(document)
            for conflict_sql, active_documents in grouped_documents.items():
                cursor.executemany(
                    f"""
                    INSERT INTO raw_documents (
                        id, source, doc_type, title, content, url, publish_time,
                        fetched_at, stock_code, stock_name, external_id, metadata, content_hash
                    )
                    VALUES (
                        %(id)s, %(source)s, %(doc_type)s, %(title)s, %(content)s, %(url)s,
                        %(publish_time)s, %(fetched_at)s, %(stock_code)s, %(stock_name)s,
                        %(external_id)s, %(metadata)s, %(content_hash)s
                    )
                    {raw_document_conflict_sql(document)}
                        source = EXCLUDED.source,
                        doc_type = EXCLUDED.doc_type,
                        title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        url = EXCLUDED.url,
                        publish_time = EXCLUDED.publish_time,
                        fetched_at = EXCLUDED.fetched_at,
                        stock_code = EXCLUDED.stock_code,
                        stock_name = EXCLUDED.stock_name,
                        external_id = EXCLUDED.external_id,
                        metadata = EXCLUDED.metadata,
                        content_hash = EXCLUDED.content_hash,
                        updated_at = NOW()
                    """,
                    [raw_document_params(document, Jsonb, fetched_at) for document in active_documents],
                )
        self.connection.commit()
        return len(documents)

    def list(self, query: RawDocumentQuery | None = None) -> list[RawDocument]:
        active_query = query or RawDocumentQuery()
        where: list[str] = []
        params: dict[str, object] = {"limit": active_query.limit}

        if active_query.start_time is not None:
            where.append("publish_time >= %(start_time)s")
            params["start_time"] = active_query.start_time
        if active_query.end_time is not None:
            where.append("publish_time <= %(end_time)s")
            params["end_time"] = active_query.end_time
        if active_query.doc_type is not None:
            where.append("doc_type = %(doc_type)s")
            params["doc_type"] = active_query.doc_type
        if active_query.source is not None:
            where.append("source = %(source)s")
            params["source"] = active_query.source
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, source, doc_type, title, content, url, publish_time, fetched_at,
                       stock_code, stock_name, external_id, metadata, content_hash
                FROM raw_documents
                {where_sql}
                ORDER BY publish_time DESC NULLS LAST, fetched_at DESC
                LIMIT %(limit)s
                """,
                params,
            )
            rows = cursor.fetchall()

        return [
            RawDocument(
                id=row[0],
                source=row[1],
                doc_type=row[2],
                title=row[3],
                content=row[4],
                url=row[5],
                publish_time=row[6],
                fetched_at=row[7],
                stock_code=row[8],
                stock_name=row[9],
                external_id=row[10],
                metadata=row[11],
                content_hash=row[12],
            )
            for row in rows
        ]


class DocumentChunkRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def replace_for_document(self, raw_document_id: str, chunks: list[DocumentChunk]) -> int:
        from psycopg.types.json import Jsonb

        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM document_chunks WHERE raw_document_id = %(raw_document_id)s", {"raw_document_id": raw_document_id})
            for chunk in chunks:
                cursor.execute(
                    """
                    INSERT INTO document_chunks (
                        id, raw_document_id, chunk_index, content, char_count,
                        metadata, content_hash, embedding_status
                    )
                    VALUES (
                        %(id)s, %(raw_document_id)s, %(chunk_index)s, %(content)s,
                        %(char_count)s, %(metadata)s, %(content_hash)s, %(embedding_status)s
                    )
                    """,
                    {
                        "id": chunk.id,
                        "raw_document_id": chunk.raw_document_id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "char_count": chunk.char_count or len(chunk.content),
                        "metadata": Jsonb(chunk.metadata),
                        "content_hash": chunk.content_hash,
                        "embedding_status": chunk.embedding_status,
                    },
                )
        self.connection.commit()
        return len(chunks)

    def list(self, query: DocumentChunkQuery | None = None) -> list[DocumentChunk]:
        active_query = query or DocumentChunkQuery()
        where: list[str] = []
        params: dict[str, object] = {"limit": active_query.limit}

        if active_query.raw_document_id is not None:
            where.append("raw_document_id = %(raw_document_id)s")
            params["raw_document_id"] = active_query.raw_document_id
        if active_query.embedding_status is not None:
            where.append("embedding_status = %(embedding_status)s")
            params["embedding_status"] = active_query.embedding_status

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, raw_document_id, chunk_index, content, char_count,
                       metadata, content_hash, embedding_status
                FROM document_chunks
                {where_sql}
                ORDER BY raw_document_id, chunk_index
                LIMIT %(limit)s
                """,
                params,
            )
            rows = cursor.fetchall()

        return [
            DocumentChunk(
                id=row[0],
                raw_document_id=row[1],
                chunk_index=row[2],
                content=row[3],
                char_count=row[4],
                metadata=row[5],
                content_hash=row[6],
                embedding_status=row[7],
            )
            for row in rows
        ]

    def update_embedding_status(self, chunk_ids: list[str], status: str) -> int:
        if not chunk_ids:
            return 0
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document_chunks
                SET embedding_status = %(status)s,
                    updated_at = NOW()
                WHERE id = ANY(%(chunk_ids)s)
                """,
                {"status": status, "chunk_ids": chunk_ids},
            )
        self.connection.commit()
        return len(chunk_ids)


class MarketSnapshotRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def upsert_many(self, snapshots: list[MarketSnapshot]) -> int:
        from psycopg.types.json import Jsonb

        with self.connection.cursor() as cursor:
            for snapshot in snapshots:
                cursor.execute(
                    """
                    INSERT INTO market_snapshots (
                        id, trade_date, code, name, open, close, high, low,
                        pct_chg, amount, turnover_rate, limit_status, source, metadata
                    )
                    VALUES (
                        %(id)s, %(trade_date)s, %(code)s, %(name)s, %(open)s, %(close)s,
                        %(high)s, %(low)s, %(pct_chg)s, %(amount)s, %(turnover_rate)s,
                        %(limit_status)s, %(source)s, %(metadata)s
                    )
                    ON CONFLICT (trade_date, code, source) DO UPDATE SET
                        name = EXCLUDED.name,
                        open = EXCLUDED.open,
                        close = EXCLUDED.close,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        pct_chg = EXCLUDED.pct_chg,
                        amount = EXCLUDED.amount,
                        turnover_rate = EXCLUDED.turnover_rate,
                        limit_status = EXCLUDED.limit_status,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    {
                        "id": snapshot.id,
                        "trade_date": snapshot.trade_date,
                        "code": snapshot.code,
                        "name": snapshot.name,
                        "open": snapshot.open,
                        "close": snapshot.close,
                        "high": snapshot.high,
                        "low": snapshot.low,
                        "pct_chg": snapshot.pct_chg,
                        "amount": snapshot.amount,
                        "turnover_rate": snapshot.turnover_rate,
                        "limit_status": snapshot.limit_status,
                        "source": snapshot.source,
                        "metadata": Jsonb(snapshot.metadata),
                    },
                )
        self.connection.commit()
        return len(snapshots)

    def list(self, query: MarketSnapshotQuery | None = None) -> list[MarketSnapshot]:
        active_query = query or MarketSnapshotQuery()
        where: list[str] = []
        params: dict[str, object] = {"limit": active_query.limit}

        if active_query.trade_date is not None:
            where.append("trade_date = %(trade_date)s")
            params["trade_date"] = active_query.trade_date
        if active_query.code is not None:
            where.append("code = %(code)s")
            params["code"] = active_query.code
        if active_query.source is not None:
            where.append("source = %(source)s")
            params["source"] = active_query.source
        if active_query.instrument_type is not None:
            where.append("metadata->>'instrument_type' = %(instrument_type)s")
            params["instrument_type"] = active_query.instrument_type

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, trade_date, code, name, open, close, high, low,
                       pct_chg, amount, turnover_rate, limit_status, source, metadata
                FROM market_snapshots
                {where_sql}
                ORDER BY trade_date DESC, code
                LIMIT %(limit)s
                """,
                params,
            )
            rows = cursor.fetchall()

        return [
            MarketSnapshot(
                id=row[0],
                trade_date=row[1],
                code=row[2],
                name=row[3],
                open=float(row[4]) if row[4] is not None else None,
                close=float(row[5]) if row[5] is not None else None,
                high=float(row[6]) if row[6] is not None else None,
                low=float(row[7]) if row[7] is not None else None,
                pct_chg=float(row[8]) if row[8] is not None else None,
                amount=float(row[9]) if row[9] is not None else None,
                turnover_rate=float(row[10]) if row[10] is not None else None,
                limit_status=row[11],
                source=row[12],
                metadata=row[13],
            )
            for row in rows
        ]


class ObservationRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def upsert(self, observation: Observation) -> Observation:
        from psycopg.types.json import Jsonb

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO observations (
                    id, trade_date, report_type, theme, related_stocks, hypothesis,
                    validation_condition, invalid_condition, priority, status,
                    outcome, review_note, source_event_ids, evidence
                )
                VALUES (
                    %(id)s, %(trade_date)s, %(report_type)s, %(theme)s, %(related_stocks)s,
                    %(hypothesis)s, %(validation_condition)s, %(invalid_condition)s,
                    %(priority)s, %(status)s, %(outcome)s, %(review_note)s,
                    %(source_event_ids)s, %(evidence)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    trade_date = EXCLUDED.trade_date,
                    report_type = EXCLUDED.report_type,
                    theme = EXCLUDED.theme,
                    related_stocks = EXCLUDED.related_stocks,
                    hypothesis = EXCLUDED.hypothesis,
                    validation_condition = EXCLUDED.validation_condition,
                    invalid_condition = EXCLUDED.invalid_condition,
                    priority = EXCLUDED.priority,
                    status = EXCLUDED.status,
                    outcome = EXCLUDED.outcome,
                    review_note = EXCLUDED.review_note,
                    source_event_ids = EXCLUDED.source_event_ids,
                    evidence = EXCLUDED.evidence,
                    updated_at = NOW()
                """,
                observation_params(observation, Jsonb),
            )
        self.connection.commit()
        return observation

    def upsert_many(self, observations: list[Observation]) -> int:
        from psycopg.types.json import Jsonb

        with self.connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO observations (
                    id, trade_date, report_type, theme, related_stocks, hypothesis,
                    validation_condition, invalid_condition, priority, status,
                    outcome, review_note, source_event_ids, evidence
                )
                VALUES (
                    %(id)s, %(trade_date)s, %(report_type)s, %(theme)s, %(related_stocks)s,
                    %(hypothesis)s, %(validation_condition)s, %(invalid_condition)s,
                    %(priority)s, %(status)s, %(outcome)s, %(review_note)s,
                    %(source_event_ids)s, %(evidence)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    trade_date = EXCLUDED.trade_date,
                    report_type = EXCLUDED.report_type,
                    theme = EXCLUDED.theme,
                    related_stocks = EXCLUDED.related_stocks,
                    hypothesis = EXCLUDED.hypothesis,
                    validation_condition = EXCLUDED.validation_condition,
                    invalid_condition = EXCLUDED.invalid_condition,
                    priority = EXCLUDED.priority,
                    status = EXCLUDED.status,
                    outcome = EXCLUDED.outcome,
                    review_note = EXCLUDED.review_note,
                    source_event_ids = EXCLUDED.source_event_ids,
                    evidence = EXCLUDED.evidence,
                    updated_at = NOW()
                """,
                [observation_params(observation, Jsonb) for observation in observations],
            )
        self.connection.commit()
        return len(observations)

    def list(self, query: ObservationQuery | None = None) -> list[Observation]:
        active_query = query or ObservationQuery()
        where: list[str] = []
        params: dict[str, object] = {"limit": active_query.limit}

        if active_query.start_date is not None:
            where.append("trade_date >= %(start_date)s")
            params["start_date"] = active_query.start_date
        if active_query.end_date is not None:
            where.append("trade_date <= %(end_date)s")
            params["end_date"] = active_query.end_date
        if active_query.trade_date is not None:
            where.append("trade_date = %(trade_date)s")
            params["trade_date"] = active_query.trade_date
        if active_query.report_type is not None:
            where.append("report_type = %(report_type)s")
            params["report_type"] = active_query.report_type
        if active_query.status is not None:
            where.append("status = %(status)s")
            params["status"] = active_query.status

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, trade_date, report_type, theme, related_stocks, hypothesis,
                       validation_condition, invalid_condition, priority, status,
                       outcome, review_note, source_event_ids, evidence
                FROM observations
                {where_sql}
                ORDER BY trade_date DESC, priority, theme
                LIMIT %(limit)s
                """,
                params,
            )
            rows = cursor.fetchall()

        return [observation_from_row(row) for row in rows]

    def update_status(self, observation_id: str, status: str, outcome: str = "", review_note: str = "") -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE observations
                SET status = %(status)s,
                    outcome = %(outcome)s,
                    review_note = %(review_note)s,
                    updated_at = NOW()
                WHERE id = %(id)s
                """,
                {
                    "id": observation_id,
                    "status": status,
                    "outcome": outcome,
                    "review_note": review_note,
                },
            )
            rowcount = cursor.rowcount
        self.connection.commit()
        return rowcount


def observation_params(observation: Observation, jsonb_factory: Any) -> dict[str, object]:
    return {
        "id": observation.id,
        "trade_date": observation.trade_date,
        "report_type": observation.report_type,
        "theme": observation.theme,
        "related_stocks": jsonb_factory(observation.related_stocks),
        "hypothesis": observation.hypothesis,
        "validation_condition": observation.validation_condition,
        "invalid_condition": observation.invalid_condition,
        "priority": observation.priority,
        "status": observation.status,
        "outcome": observation.outcome,
        "review_note": observation.review_note,
        "source_event_ids": jsonb_factory(observation.source_event_ids),
        "evidence": jsonb_factory(observation.evidence),
    }


def observation_from_row(row) -> Observation:
    return Observation(
        id=row[0],
        trade_date=row[1],
        report_type=row[2],
        theme=row[3],
        related_stocks=row[4],
        hypothesis=row[5],
        validation_condition=row[6],
        invalid_condition=row[7],
        priority=row[8],
        status=row[9],
        outcome=row[10],
        review_note=row[11],
        source_event_ids=row[12],
        evidence=row[13],
    )
