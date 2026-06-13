from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from app.config import Settings, load_settings


SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS raw_documents (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        doc_type TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        url TEXT NOT NULL DEFAULT '',
        publish_time TIMESTAMPTZ,
        fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        stock_code TEXT NOT NULL DEFAULT '',
        stock_name TEXT NOT NULL DEFAULT '',
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        external_id TEXT NOT NULL DEFAULT '',
        content_hash TEXT NOT NULL UNIQUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "ALTER TABLE raw_documents ADD COLUMN IF NOT EXISTS external_id TEXT NOT NULL DEFAULT ''",
    "UPDATE raw_documents SET external_id = metadata->>'page_id' WHERE source = 'notion' AND external_id = '' AND metadata ? 'page_id'",
    """
    DELETE FROM raw_documents
    WHERE id IN (
        SELECT id
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY source, external_id
                       ORDER BY fetched_at DESC, updated_at DESC, id DESC
                   ) AS row_number
            FROM raw_documents
            WHERE external_id <> ''
        ) ranked
        WHERE row_number > 1
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_documents_source_external_id ON raw_documents (source, external_id) WHERE external_id <> ''",
    "CREATE INDEX IF NOT EXISTS idx_raw_documents_publish_time ON raw_documents (publish_time)",
    "CREATE INDEX IF NOT EXISTS idx_raw_documents_doc_type ON raw_documents (doc_type)",
    "CREATE INDEX IF NOT EXISTS idx_raw_documents_source ON raw_documents (source)",
    """
    CREATE TABLE IF NOT EXISTS document_chunks (
        id TEXT PRIMARY KEY,
        raw_document_id TEXT NOT NULL REFERENCES raw_documents(id) ON DELETE CASCADE,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        char_count INTEGER NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        content_hash TEXT NOT NULL UNIQUE,
        embedding_status TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (raw_document_id, chunk_index)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_document_chunks_raw_document_id ON document_chunks (raw_document_id)",
    "CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_status ON document_chunks (embedding_status)",
    """
    CREATE TABLE IF NOT EXISTS market_snapshots (
        id TEXT PRIMARY KEY,
        trade_date DATE NOT NULL,
        code TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        open NUMERIC,
        close NUMERIC,
        high NUMERIC,
        low NUMERIC,
        pct_chg NUMERIC,
        amount NUMERIC,
        turnover_rate NUMERIC,
        limit_status TEXT NOT NULL DEFAULT 'none',
        source TEXT NOT NULL DEFAULT '',
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (trade_date, code, source)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_market_snapshots_trade_date ON market_snapshots (trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_market_snapshots_code ON market_snapshots (code)",
    """
    CREATE TABLE IF NOT EXISTS observations (
        id TEXT PRIMARY KEY,
        trade_date DATE NOT NULL,
        report_type TEXT NOT NULL,
        theme TEXT NOT NULL,
        related_stocks JSONB NOT NULL DEFAULT '[]'::jsonb,
        hypothesis TEXT NOT NULL,
        validation_condition TEXT NOT NULL,
        invalid_condition TEXT NOT NULL,
        priority TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        outcome TEXT NOT NULL DEFAULT '',
        review_note TEXT NOT NULL DEFAULT '',
        source_event_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_observations_trade_date ON observations (trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_observations_report_type ON observations (report_type)",
    "CREATE INDEX IF NOT EXISTS idx_observations_status ON observations (status)",
)


def _import_psycopg():
    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing dependency: run `pip install -r requirements.txt` first.") from exc
    return psycopg


@contextmanager
def connect(settings: Settings | None = None) -> Iterator[object]:
    psycopg = _import_psycopg()
    active_settings = settings or load_settings()
    with psycopg.connect(
        active_settings.database_url,
        connect_timeout=active_settings.database_connect_timeout,
    ) as connection:
        yield connection


def init_db(settings: Settings | None = None) -> None:
    with connect(settings) as connection:
        with connection.cursor() as cursor:
            for statement in SCHEMA_SQL:
                cursor.execute(statement)
        connection.commit()
