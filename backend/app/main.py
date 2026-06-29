"""FastAPI entrypoint. Serves the API under /api and (in prod) the built React app."""
from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse

from . import db, security
from .config import get_settings
from .routers import agent, chat, conversations, documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

settings = get_settings()

app = FastAPI(title="RAG Chatbot", version="0.1.0")

# Security headers on every response.
app.add_middleware(security.SecurityHeadersMiddleware)

# CORS scoped to the known frontend origins, only the methods/headers we use.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Idempotent (CREATE TABLE IF NOT EXISTS) — run at import so the schema exists
# under uvicorn and under TestClient (which doesn't fire startup events).
db.init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "model": settings.chat_model}


# Rate-limit the expensive / abusable endpoints (LLM calls, uploads).
app.include_router(chat.router, prefix="/api", dependencies=[Depends(security.rate_limit)])
app.include_router(agent.router, prefix="/api", dependencies=[Depends(security.rate_limit)])
app.include_router(documents.router, prefix="/api", dependencies=[Depends(security.rate_limit)])
app.include_router(conversations.router, prefix="/api")


# In production (single container) the built React app lives in frontend/dist.
# Serve real files when they exist; fall back to index.html for SPA routes.
if settings.frontend_dist.exists():

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        candidate = settings.frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(settings.frontend_dist / "index.html")
