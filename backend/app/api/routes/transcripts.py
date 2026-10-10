from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import pool
from app.models_config import get_model
from app.schemas.filters import TranscriptFilters, filters_query
from app.schemas.transcript import Facets, SearchResponse, Stats, Transcript
from app.services.search import facets, search

router = APIRouter(prefix="/api", tags=["transcripts"])


@router.get("/search", response_model=SearchResponse)
def search_transcripts(
    q: str = Query("", max_length=300, description="Keywords; supports \"quoted phrases\", OR, and -exclude"),
    filters: TranscriptFilters = Depends(filters_query),
    sort: Literal["relevance", "recent", "questions", "marks"] = "relevance",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Browse: filtered listing, narrowed by keywords when q is given."""
    total, rows = search(q, filters, limit, offset, sort)
    return {"total": total, "hits": rows}


@router.get("/facets", response_model=Facets)
def transcript_facets(q: str = Query("", max_length=300), filters: TranscriptFilters = Depends(filters_query)):
    """Counts per tag for the Browse sidebar, given the current keywords and filters."""
    return facets(filters, q)


@router.get("/transcripts/{transcript_id}", response_model=Transcript)
def get_transcript(transcript_id: str):
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM transcripts WHERE id = %s", (transcript_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return row


@router.get("/stats", response_model=Stats)
def stats():
    with pool.connection() as conn:
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM transcripts) AS transcripts, (SELECT count(*) FROM held) AS held,"
            " (SELECT count(*) FROM chunks) AS chunks").fetchone()

        def facet(col: str) -> list[dict]:
            return conn.execute(
                f"SELECT {col}::text AS value, count(*) AS count FROM transcripts GROUP BY {col} ORDER BY count DESC"
            ).fetchall()

        return {**counts, "boards": facet("board"), "years": facet("cse_year"), "exams": facet("exam"),
                "llm_model": get_model("model_1").id}
