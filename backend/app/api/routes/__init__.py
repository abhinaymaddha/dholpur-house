from app.api.routes.ask import router as ask_router
from app.api.routes.health import router as health_router
from app.api.routes.transcripts import router as transcripts_router

__all__ = ["ask_router", "health_router", "transcripts_router"]
