"""
Database connection pool and schema.

Postgres with pgvector: full-text search (tsvector) for keyword search, vector similarity for RAG.
The schema is idempotent and applied on startup and by the ingest command.
"""

from __future__ import annotations

from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

EMBED_DIM = settings.embed_dim

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS transcripts (
    id               text PRIMARY KEY,
    message_ids      int[] NOT NULL,
    posted_at        timestamp NOT NULL,
    telegram_url     text NOT NULL,
    board            text NOT NULL,
    alias            text,
    interview_date   text,
    daf              text,
    optional_subject text,
    pt_marks         int,
    exam             text NOT NULL,
    cse_year         int NOT NULL,
    reactions        int NOT NULL DEFAULT 0,
    duplicates       text[] NOT NULL DEFAULT '{{}}',
    text             text NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(daf, '') || ' ' || coalesce(optional_subject, '')), 'A') ||
        setweight(to_tsvector('english', text), 'B')
    ) STORED
);
CREATE INDEX IF NOT EXISTS transcripts_tsv ON transcripts USING gin (tsv);
CREATE INDEX IF NOT EXISTS transcripts_filters ON transcripts (cse_year, board, exam);

-- Units that are not clearly one marked transcript; kept for later review, not searchable.
CREATE TABLE IF NOT EXISTS held (
    id          text PRIMARY KEY,
    reason      text NOT NULL,
    message_ids int[] NOT NULL,
    posted_at   timestamp NOT NULL,
    text        text NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id            bigserial PRIMARY KEY,
    transcript_id text NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    seq           int NOT NULL,
    section       text NOT NULL,
    text          text NOT NULL,
    embedding     vector({EMBED_DIM}) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_tsv ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_transcript ON chunks (transcript_id);
"""


def _configure(conn) -> None:
    register_vector(conn)


pool = ConnectionPool(settings.database_url, min_size=1, max_size=8, open=False,
                      kwargs={"row_factory": dict_row}, configure=_configure)


def init_schema(conn) -> None:
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    conn.execute(SCHEMA)
