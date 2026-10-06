"""RAG endpoint: retrieve transcripts, then stream an LLM answer as server-sent events.

Events: `sources` (JSON list, sent first), `delta` (answer text, many), `error`, `done`.
"""

import json
import logging

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.schemas.ask import AskRequest
from app.services.llm import LLMError, stream_answer
from app.services.retrieval import retrieve

router = APIRouter(prefix="/api", tags=["ask"])
logger = logging.getLogger(__name__)


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(jsonable_encoder(data), ensure_ascii=False)}\n\n"


@router.post("/ask")
def ask(req: AskRequest):
    def events():
        sources = retrieve(req.question, req.filters, top_k=req.top_k)
        yield _sse("sources", sources)
        if not sources:
            yield _sse("error", "No transcripts matched. Try different words or remove filters.")
            return
        try:
            for delta in stream_answer(req.question, sources):
                yield _sse("delta", delta)
        except LLMError as e:
            logger.warning("LLM failed: %s", e)
            yield _sse("error", str(e))
            return
        yield _sse("done", {})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
