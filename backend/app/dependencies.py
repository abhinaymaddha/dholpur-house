"""Wiring: one shared instance of each repository and service, handed to routes with FastAPI Depends.

Tests swap any of these with app.dependency_overrides[get_x] = lambda: fake.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Request

from app.config import settings
from app.interview.background import BackgroundWork
from app.interview.bank import QuestionBank
from app.interview.questions import GeneratedQuestionSource, OpeningQuestionSource, QuestionSource, RealQuestionSource
from app.repositories import (
    ChunkRepository, InterviewRepository, NewsRepository, QuestionRepository, TranscriptRepository,
)
from app.services.news import NewsService
from app.services.rate_limit import RateLimiter
from app.services.retrieval import HybridRetriever


@lru_cache
def get_transcripts() -> TranscriptRepository:
    return TranscriptRepository()


@lru_cache
def get_interviews() -> InterviewRepository:
    return InterviewRepository()


@lru_cache
def get_retriever() -> HybridRetriever:
    return HybridRetriever(ChunkRepository(), get_transcripts())


@lru_cache
def get_news() -> NewsService:
    return NewsService(NewsRepository())


@lru_cache
def get_bank() -> QuestionBank:
    return QuestionBank(QuestionRepository())


@lru_cache
def get_question_sources() -> dict[str, QuestionSource]:
    bank = get_bank()
    return {"generated": GeneratedQuestionSource(bank, get_news()), "real": RealQuestionSource(bank),
            "instant": RealQuestionSource(bank, clean=True), "opening": OpeningQuestionSource(bank)}


@lru_cache
def get_background() -> BackgroundWork:
    return BackgroundWork()


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(settings.rate_per_minute, settings.rate_per_day, settings.ai_daily_budget)


def client_ip(request: Request) -> str:
    """The visitor's address. nginx sets X-Real-IP from the proxy chain (see frontend/nginx.conf), overwriting any
    value the visitor sent, so it can't be spoofed through the public site."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
