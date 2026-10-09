from app.api.routes.admin import router as admin_router
from app.api.routes.ask import router as ask_router
from app.api.routes.health import router as health_router
from app.api.routes.interview import router as interview_router
from app.api.routes.transcripts import router as transcripts_router

__all__ = ["admin_router", "ask_router", "health_router", "interview_router", "transcripts_router"]
