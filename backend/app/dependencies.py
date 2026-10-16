"""Wiring: one shared instance of each repository and service, handed to routes with FastAPI Depends.

Tests swap any of these with app.dependency_overrides[get_x] = lambda: fake.
"""

from __future__ import annotations

from functools import lru_cache

from app.interview.bank import QuestionBank
from app.interview.questions import GeneratedQuestionSource, QuestionSource, RealQuestionSource
from app.repositories import (
    ChunkRepository, InterviewRepository, NewsRepository, QuestionRepository, TranscriptRepository,
)
from app.services.news import NewsService
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
    return {"generated": GeneratedQuestionSource(bank, get_news()), "real": RealQuestionSource(bank)}
