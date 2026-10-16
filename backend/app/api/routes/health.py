from fastapi import APIRouter, Depends

from app.dependencies import get_transcripts
from app.repositories import TranscriptRepository

router = APIRouter(tags=["health"])


@router.get("/health")
def health(repo: TranscriptRepository = Depends(get_transcripts)):
    repo.ping()
    return {"status": "ok"}
