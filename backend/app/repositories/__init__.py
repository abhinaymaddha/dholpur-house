"""Data access. Everything else goes through these repositories; no SQL outside this package
(except the schema in app/database.py)."""

from app.repositories.chunks import ChunkRepository
from app.repositories.interviews import InterviewRepository
from app.repositories.news import NewsRepository
from app.repositories.questions import QuestionRepository
from app.repositories.transcripts import TranscriptRepository

__all__ = ["ChunkRepository", "InterviewRepository", "NewsRepository", "QuestionRepository", "TranscriptRepository"]
