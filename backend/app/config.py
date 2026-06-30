"""Application settings, loaded from environment / the project .env file."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# .../learning-langchain  (project root, two levels up from this file's app/ dir)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Fireworks / LangChain ---
    fireworks_api_key: str = ""
    chat_model: str = "accounts/fireworks/models/kimi-k2p6"
    embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    temperature: float = 0.2

    # --- RAG knobs ---
    top_k: int = 4
    chunk_size: int = 1000
    chunk_overlap: int = 150
    max_history: int = 10  # how many prior messages to feed back into the prompt

    # --- security / limits ---
    max_upload_mb: int = 20            # reject uploads larger than this
    max_message_chars: int = 8000      # reject chat messages longer than this
    # When False (default) the knowledge base is READ-ONLY to visitors: the
    # /api/documents upload endpoint is disabled and the `ingest_url` tool is
    # withheld. Curate the KB privately via backend/knowledge/*.md + re-seed.
    allow_public_upload: bool = False
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 30    # per client IP, on chat + upload

    # --- cost guardrail (hard daily kill-switch on estimated LLM spend) ---
    daily_cost_cap_usd: float = 1.0            # per UTC day; <= 0 disables the cap
    usd_per_million_input_tokens: float = 0.9  # estimate — tune to your provider/model
    usd_per_million_output_tokens: float = 0.9 # estimate — tune to your provider/model

    # --- agent ---
    agent_model: str = ""              # tool-calling model; defaults to chat_model
    agent_max_steps: int = 6           # max tool-call iterations per turn
    tavily_api_key: str = ""           # optional; enables Tavily web search

    # --- paths & server ---
    data_dir: Path = PROJECT_ROOT / "backend" / "data"
    knowledge_dir: Path = PROJECT_ROOT / "backend" / "knowledge"
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    # Origins allowed to embed the app in an <iframe> (CSP frame-ancestors).
    # Empty = framing is blocked entirely (the safe default). Set to your site,
    # e.g. ["https://pyrotheum1702.com","https://www.pyrotheum1702.com"].
    embed_origins: List[str] = []

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "app.db"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # Make sure the working directories exist.
    for d in (s.data_dir, s.chroma_dir, s.upload_dir):
        d.mkdir(parents=True, exist_ok=True)
    # langchain-fireworks reads FIREWORKS_API_KEY from the environment; mirror it
    # there so both ChatFireworks and FireworksEmbeddings pick it up.
    if s.fireworks_api_key and not os.environ.get("FIREWORKS_API_KEY"):
        os.environ["FIREWORKS_API_KEY"] = s.fireworks_api_key
    return s
