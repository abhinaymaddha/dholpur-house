"""
UPSC Interview Transcripts - API

Keyword search and RAG question answering over Personality Test transcripts.
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg import connect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin_router, ask_router, health_router, interview_router, transcripts_router
from app.config import settings
from app.database import init_schema, pool
from app.ingest.pipeline import SEED_FILE
from app.models_config import all_models
from app.services import ingest_job, news
from app.services.embeddings import embed_one

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the pgvector extension before the pool opens: pooled connections register the vector type.
    with connect(settings.database_url, autocommit=True) as conn:
        init_schema(conn)
        empty = conn.execute("SELECT NOT EXISTS (SELECT 1 FROM transcripts)").fetchone()[0]
    pool.open(wait=True)
    if empty and settings.seed_on_empty and SEED_FILE.exists():
        # Fresh database: load the committed seed in the background (takes a few minutes).
        logger.info("Database is empty; loading seed data from %s", SEED_FILE.name)
        ingest_job.start(SEED_FILE, label=f"seed: {SEED_FILE.name}")
    else:
        # Load the embedding model in the background so the first /api/ask isn't slow.
        threading.Thread(target=embed_one, args=("warm up",), daemon=True).start()
    news.refresh_in_background()   # current-affairs feeds for Interview mode
    logger.info("Started %s (models: %s)", settings.app_name, {k: m.id for k, m in all_models().items()})
    yield
    pool.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(transcripts_router)
app.include_router(ask_router)
app.include_router(interview_router)
app.include_router(admin_router)
