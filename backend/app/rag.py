"""Vector store: loading, chunking, embedding (Fireworks), Chroma, and seeding.

Generation now lives in the agent (agent.py) — retrieval is exposed to the model
as the `search_documents` tool. This module just owns the knowledge store.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from .config import get_settings

logger = logging.getLogger("ragchat")


@lru_cache
def get_embeddings():
    from langchain_fireworks import FireworksEmbeddings

    return FireworksEmbeddings(model=get_settings().embedding_model)


@lru_cache
def get_vectorstore():
    from langchain_chroma import Chroma

    s = get_settings()
    return Chroma(
        collection_name="docs",
        embedding_function=get_embeddings(),
        persist_directory=str(s.chroma_dir),
    )


def _load(path: str):
    """Pick a loader by extension and return a list of LangChain Documents."""
    if path.lower().endswith(".pdf"):
        from langchain_community.document_loaders import PyPDFLoader

        return PyPDFLoader(path).load()
    from langchain_community.document_loaders import TextLoader

    return TextLoader(path, encoding="utf-8").load()


def ingest_path(path: str, source_name: str) -> int:
    """Load, chunk, embed, and store a file. Returns the number of chunks added."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    s = get_settings()
    docs = _load(path)
    for d in docs:
        d.metadata["source"] = source_name

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.chunk_size, chunk_overlap=s.chunk_overlap
    )
    chunks = splitter.split_documents(docs)
    if chunks:
        get_vectorstore().add_documents(chunks)
    return len(chunks)


def retrieve(question: str):
    s = get_settings()
    return get_vectorstore().similarity_search(question, k=s.top_k)


def seed_knowledge() -> int:
    """Ingest the knowledge pack (knowledge/) once, on first startup.

    A sentinel file prevents re-embedding on every boot. To re-seed after editing
    the knowledge files, delete `<data_dir>/.seeded` (or the whole data dir).
    Returns the number of chunks seeded (0 if already seeded or nothing to do).
    """
    from . import db

    s = get_settings()
    sentinel = s.data_dir / ".seeded"
    if sentinel.exists() or not s.knowledge_dir.exists():
        return 0

    total = 0
    for path in sorted(s.knowledge_dir.glob("*")):
        if path.suffix.lower() not in (".md", ".txt", ".pdf"):
            continue
        if path.name.lower() == "readme.md":  # meta, not content
            continue
        try:
            n = ingest_path(str(path), path.name)
            db.add_document(path.name, n)
            total += n
            logger.info("seeded %s (%d chunks)", path.name, n)
        except Exception:
            logger.exception("failed to seed %s", path.name)

    if total > 0:  # only mark seeded if something actually landed (e.g. key present)
        sentinel.write_text("seeded\n", encoding="utf-8")
    return total
