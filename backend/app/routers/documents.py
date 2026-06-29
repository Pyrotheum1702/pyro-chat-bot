"""Document upload + listing. Upload triggers RAG ingestion."""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from .. import db, rag, security
from ..config import get_settings

router = APIRouter()
logger = logging.getLogger("ragchat")

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


@router.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    settings = get_settings()

    # 1. Sanitize the filename (defends against path traversal).
    name = security.safe_filename(file.filename or "upload")
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    dest = security.ensure_within(settings.upload_dir, settings.upload_dir / name)

    # 2. Stream to disk with a size cap (defends against giant-file DoS).
    max_bytes = settings.max_upload_mb * 1024 * 1024
    size = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {settings.max_upload_mb} MB limit.",
                    )
                out.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)  # remove partial upload
        raise
    except Exception:
        logger.exception("failed to save upload")
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not save the uploaded file.")

    # 3. Ingest. Don't leak internal errors to the client.
    try:
        chunks = await run_in_threadpool(rag.ingest_path, str(dest), name)
    except Exception:
        logger.exception("ingestion failed for %s", name)
        raise HTTPException(status_code=500, detail="Failed to process the document.")

    if chunks == 0:
        raise HTTPException(status_code=400, detail="No text could be extracted from the file.")

    return db.add_document(name, chunks)


@router.get("/documents")
def list_documents():
    return db.list_documents()
