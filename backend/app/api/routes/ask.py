"""RAG endpoint: retrieve transcripts, then stream an LLM answer as server-sent events.

Events: `sources` (JSON list, sent first), `delta` (answer text, many), `error`, `done`.
"""

import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.dependencies import client_ip, get_rate_limiter, get_retriever
from app.errors import AppError
from app.schemas.ask import AskRequest
from app.services.answer import stream_answer
from app.services.rate_limit import RateLimiter
from app.services.retrieval import HybridRetriever

router = APIRouter(prefix="/api", tags=["ask"])
logger = logging.getLogger(__name__)


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(jsonable_encoder(data), ensure_ascii=False)}\n\n"


@router.post("/ask")
def ask(req: AskRequest, request: Request, retriever: HybridRetriever = Depends(get_retriever),
        limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.check(client_ip(request))   # before the stream starts, so a refusal is a plain 429
    def events():
        sources = retriever.retrieve(req.question, req.filters, top_k=req.top_k, q=req.q)
        yield _sse("sources", sources)
        if not sources:
            yield _sse("error", "No transcripts matched. Try different words or remove filters.")
            return
        try:
            for delta in stream_answer(req.question, sources):
                yield _sse("delta", delta)
        except AppError as e:
            logger.warning("LLM failed: %s", e)
            yield _sse("error", str(e))
            return
        yield _sse("done", {})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
