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

-- Filter tags (app/ingest/tags.py) and the reader outline (app/ingest/structure.py).
ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS background   text[] NOT NULL DEFAULT '{{}}';
ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS optional_tag text;
ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS states       text[] NOT NULL DEFAULT '{{}}';
ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS interests    text[] NOT NULL DEFAULT '{{}}';
ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS topics       text[] NOT NULL DEFAULT '{{}}';
ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS question_count int NOT NULL DEFAULT 0;
ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS structure    jsonb;
CREATE INDEX IF NOT EXISTS transcripts_topics ON transcripts USING gin (topics);
CREATE INDEX IF NOT EXISTS transcripts_profile ON transcripts USING gin (background, states, interests);

-- Units that are not clearly one marked transcript; kept for later review, not searchable.
CREATE TABLE IF NOT EXISTS held (
    id          text PRIMARY KEY,
    reason      text NOT NULL,
    message_ids int[] NOT NULL,
    posted_at   timestamp NOT NULL,
    text        text NOT NULL
);

-- Every question asked in a transcript, for Interview mode. prev_id links a follow-up to the question before it.
CREATE TABLE IF NOT EXISTS questions (
    id            bigserial PRIMARY KEY,
    transcript_id text NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    seq           int NOT NULL,
    member        text NOT NULL,
    text          text NOT NULL,
    topics        text[] NOT NULL DEFAULT '{{}}',
    prev_id       bigint,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX IF NOT EXISTS questions_topics ON questions USING gin (topics);
CREATE INDEX IF NOT EXISTS questions_tsv ON questions USING gin (tsv);
CREATE INDEX IF NOT EXISTS questions_transcript ON questions (transcript_id);

-- Current-affairs articles (app/services/news.py), tagged with interview topics.
CREATE TABLE IF NOT EXISTS news_items (
    url          text PRIMARY KEY,
    source       text NOT NULL,
    title        text NOT NULL,
    summary      text NOT NULL DEFAULT '',
    published_at timestamptz NOT NULL,
    topics       text[] NOT NULL
);
CREATE INDEX IF NOT EXISTS news_items_topics ON news_items USING gin (topics);
CREATE TABLE IF NOT EXISTS news_fetches (source text PRIMARY KEY, fetched_at timestamptz NOT NULL);

-- Interview mode conversations. A turn is one question and, once answered, its evaluation.
CREATE TABLE IF NOT EXISTS interview_sessions (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS interview_turns (
    id          bigserial PRIMARY KEY,
    session_id  uuid NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    main_index  int NOT NULL,          -- 1, 2, 3 ... per main question
    depth       int NOT NULL,          -- 0 = main question, 1-2 = follow-ups
    topic       text NOT NULL,
    question    text NOT NULL,
    source      jsonb NOT NULL,        -- where the question came from (past transcript, article, DAF, generated)
    answer      text,
    evaluation  jsonb,
    mode        text
);
CREATE INDEX IF NOT EXISTS interview_turns_session ON interview_turns (session_id, id);

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
