from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_transcripts
from app.models_config import get_model
from app.repositories import TranscriptRepository
from app.schemas.filters import TranscriptFilters, filters_query
from app.schemas.transcript import Facets, SearchResponse, Stats, Transcript

router = APIRouter(prefix="/api", tags=["transcripts"])


@router.get("/search", response_model=SearchResponse)
def search_transcripts(
    q: str = Query("", max_length=300, description="Keywords; supports \"quoted phrases\", OR, and -exclude"),
    filters: TranscriptFilters = Depends(filters_query),
    sort: Literal["relevance", "recent", "questions", "marks"] = "relevance",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: TranscriptRepository = Depends(get_transcripts),
):
    """Browse: filtered listing, narrowed by keywords when q is given."""
    total, rows = repo.search(q, filters, limit, offset, sort)
    return {"total": total, "hits": rows}


@router.get("/facets", response_model=Facets)
def transcript_facets(q: str = Query("", max_length=300), filters: TranscriptFilters = Depends(filters_query),
                      repo: TranscriptRepository = Depends(get_transcripts)):
    """Counts per tag for the Browse sidebar, given the current keywords and filters."""
    return repo.facets(filters, q)


@router.get("/transcripts/{transcript_id}", response_model=Transcript)
def get_transcript(transcript_id: str, repo: TranscriptRepository = Depends(get_transcripts)):
    row = repo.get(transcript_id)
    if not row:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return row


@router.get("/stats", response_model=Stats)
def stats(repo: TranscriptRepository = Depends(get_transcripts)):
    return {**repo.stats(), "llm_model": get_model("model_1").id}
