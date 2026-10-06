from fastapi import APIRouter

from app.database import pool

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}
