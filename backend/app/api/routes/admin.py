"""Admin endpoints: load a new Telegram export over HTTP, so a hosted deployment needs no shell access.

Disabled unless ADMIN_TOKEN is set. Send it as `Authorization: Bearer <token>`.

    curl -H "Authorization: Bearer $ADMIN_TOKEN" -F "files=@messages.html" https://<host>/api/admin/ingest
    curl -H "Authorization: Bearer $ADMIN_TOKEN" https://<host>/api/admin/ingest
"""

import re
import secrets
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status

from app.config import settings
from app.services import ingest_job

router = APIRouter(prefix="/api/admin", tags=["admin"])

EXPORT_FILE = re.compile(r"^messages\d*\.html$")   # Telegram splits big exports into messages2.html, ...
MAX_FILE_BYTES = 60 * 1024 * 1024


def require_admin(authorization: str = Header(default="")) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=404, detail="Not found")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, settings.admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _save_uploads(files: list[UploadFile], names: list[str]) -> Path:
    export_dir = Path(tempfile.mkdtemp(prefix="export-"))
    try:
        for f, name in zip(files, names):
            with open(export_dir / name, "wb") as out:
                copied = 0
                while chunk := f.file.read(1024 * 1024):
                    copied += len(chunk)
                    if copied > MAX_FILE_BYTES:
                        raise HTTPException(status_code=413, detail=f"{name} is larger than 60 MB")
                    out.write(chunk)
    except BaseException:
        shutil.rmtree(export_dir, ignore_errors=True)
        raise
    return export_dir


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_admin)])
def start_ingest(files: list[UploadFile] = File(..., description="messages.html (and messages2.html, ...)")):
    """Replace all data with this Telegram export."""
    names = [Path(f.filename or "").name for f in files]
    bad = [n for n in names if not EXPORT_FILE.match(n)]
    if bad:
        raise HTTPException(status_code=422, detail=f"Expected messages*.html files from a Telegram export, got {bad}")
    if ingest_job.status().get("state") == "running":
        raise HTTPException(status_code=409, detail="An ingest is already running")
    export_dir = _save_uploads(files, names)
    try:
        ingest_job.start(export_dir, label=f"upload: {', '.join(names)}", cleanup=export_dir)
    except ingest_job.IngestRunning:
        shutil.rmtree(export_dir, ignore_errors=True)
        raise HTTPException(status_code=409, detail="An ingest is already running")
    return {"state": "running", "files": names}


@router.get("/ingest", dependencies=[Depends(require_admin)])
def ingest_status():
    return ingest_job.status()
