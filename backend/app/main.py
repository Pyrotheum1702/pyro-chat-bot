"""FastAPI entrypoint. Serves the API under /api and (in prod) the built React app.

The chat endpoint runs a single tool-using agent (agentic RAG): the model decides
when to search the knowledge base (`search_documents`), search the web, etc.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse

from . import cost, db, rag, security
from .config import get_settings
from .routers import chat, conversations, documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ragchat")

settings = get_settings()

# Idempotent (CREATE TABLE IF NOT EXISTS) — at import so the schema exists under
# uvicorn and under TestClient (which doesn't run the lifespan).
db.init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed the "About Me" knowledge pack once (uses Fireworks embeddings → network).
    # Runs only on a real server start, not under TestClient, so tests stay offline.
    try:
        seeded = await asyncio.to_thread(rag.seed_knowledge)
        if seeded:
            logger.info("seeded %d chunks from the knowledge pack", seeded)
    except Exception:
        logger.exception("knowledge seeding failed")
    yield


app = FastAPI(title="Portfolio Chatbot", version="0.1.0", lifespan=lifespan)

app.add_middleware(security.SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "model": settings.chat_model,
        "daily_cost_cap_usd": settings.daily_cost_cap_usd,
        "spent_today_usd": round(cost.METER.spent_today(), 4),
    }


# Rate-limit the expensive / abusable endpoints (LLM calls, uploads).
# Chat also enforces the daily cost cap (hard kill-switch on LLM spend).
app.include_router(
    chat.router,
    prefix="/api",
    dependencies=[Depends(security.rate_limit), Depends(cost.cost_guard)],
)
app.include_router(documents.router, prefix="/api", dependencies=[Depends(security.rate_limit)])
app.include_router(conversations.router, prefix="/api")


# In production (single container) the built React app lives in frontend/dist.
if settings.frontend_dist.exists():

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        candidate = settings.frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(settings.frontend_dist / "index.html")
