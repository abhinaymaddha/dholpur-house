"""
UPSC Interview Transcripts - API

Keyword search and RAG question answering over Personality Test transcripts.
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ask_router, health_router, transcripts_router
from app.config import settings
from app.database import init_schema, pool
from app.services.embeddings import embed_one

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open(wait=True)
    with pool.connection() as conn:
        init_schema(conn)
    # Load the embedding model in the background so the first /api/ask isn't slow.
    threading.Thread(target=embed_one, args=("warm up",), daemon=True).start()
    logger.info("Started %s (LLM: %s)", settings.app_name, settings.llm_model)
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
