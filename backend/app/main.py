"""
Dholpur House - API

Keyword search and RAG question answering over Personality Test transcripts.
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin_router, ask_router, health_router, interview_router, transcripts_router
from app.config import settings
from app.database import pool
from app.dependencies import get_news
from app.errors import AppError, ProviderError
from app.ingest.pipeline import SEED_FILE
from app.models_config import all_models
from app.repositories import TranscriptRepository
from app.services import ingest_job
from app.services.embeddings import embed_one

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    empty = TranscriptRepository.prepare_database()
    pool.open(wait=True)
    if empty and settings.seed_on_empty and SEED_FILE.exists():
        # Fresh database: load the committed seed in the background (takes a few minutes).
        logger.info("Database is empty; loading seed data from %s", SEED_FILE.name)
        ingest_job.start(SEED_FILE, label=f"seed: {SEED_FILE.name}")
    else:
        # Load the embedding model in the background so the first /api/ask isn't slow.
        threading.Thread(target=embed_one, args=("warm up",), daemon=True).start()
    get_news().refresh_in_background()   # current-affairs feeds for Interview mode
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


@app.exception_handler(AppError)
def app_error(request: Request, exc: AppError) -> JSONResponse:
    detail = f"The AI model failed: {exc}" if isinstance(exc, ProviderError) else str(exc)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


app.include_router(health_router)
app.include_router(transcripts_router)
app.include_router(ask_router)
app.include_router(interview_router)
app.include_router(admin_router)
