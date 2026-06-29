# Learning LangChain — RAG Chatbot

**Status:** 🟨 In progress · **Type:** Self-directed learning build

A chatbot web app that answers questions grounded in documents you upload
(Retrieval-Augmented Generation), built to learn LangChain end-to-end.
FastAPI + React, streaming responses, persistent chat history, Dockerized.

See the [Definition of Done](DEFINITION_OF_DONE.md) for the full scope and acceptance criteria.

## What it does

- Upload `.pdf` / `.txt` / `.md` documents → they're chunked, embedded, and stored in a vector DB.
- Ask questions → the app retrieves the most relevant chunks and the LLM answers from them, **streaming** token-by-token, with the **sources** shown.
- Conversations and the vector store **persist** across restarts.

## Architecture

```
React SPA (Vite)                         dev :5173  ·  prod: served by backend
  │  POST /api/chat (SSE stream) · POST/GET /api/documents · GET /api/conversations
  ▼
FastAPI backend (:8017)
  ├─ RAG (LangChain): retrieve top-k ─▶ prompt ─▶ Fireworks LLM ─▶ stream tokens
  ├─ Ingestion: load ─▶ chunk ─▶ embed (Fireworks) ─▶ Chroma
  ├─ Chroma   (vectors, on disk)
  └─ SQLite   (conversations + messages)
```

## Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI + Uvicorn |
| RAG | LangChain (`langchain-fireworks`, `langchain-chroma`, text splitters, community loaders) |
| LLM | Fireworks — `accounts/fireworks/models/kimi-k2p6` (configurable) |
| Embeddings | Fireworks — `nomic-ai/nomic-embed-text-v1.5` |
| Vector store | Chroma (persisted to disk) |
| History | SQLite |
| Frontend | React (Vite), SSE streaming client |
| Packaging | Single Docker image (FastAPI serves the built React app) |

## Prerequisites

- Python 3.9+ and Node 18+ (this repo was built on Python 3.9 / Node 22).
- A **Fireworks API key** in `.env` (`cp .env.example .env`, then fill in `FIREWORKS_API_KEY`).

## Quickstart — local dev (two terminals)

**1. Backend** (auto-loads `../.env` for the key):
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8017
```

**2. Frontend:**
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api -> :8017)
```

Open **http://localhost:5173**, upload a document, and ask about it.

## Run with Docker (single container)

```bash
# from this folder, with .env present (containing FIREWORKS_API_KEY)
docker compose up --build
```
Open **http://localhost:8017**. Chroma + SQLite + uploads persist in the `ragdata` volume.

## Configuration

All optional except the key. Set in `.env` (see [.env.example](.env.example)):

| Var | Default | Meaning |
|-----|---------|---------|
| `FIREWORKS_API_KEY` | — | **Required.** Fireworks key. |
| `CHAT_MODEL` | `accounts/fireworks/models/kimi-k2p6` | Chat model id. |
| `EMBEDDING_MODEL` | `nomic-ai/nomic-embed-text-v1.5` | Embedding model id. |
| `TEMPERATURE` | `0.2` | Sampling temperature. |
| `TOP_K` | `4` | Chunks retrieved per question. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `150` | Splitter settings. |
| `MAX_HISTORY` | `10` | Prior messages fed back into the prompt. |
| `DATA_DIR` | `backend/data` | Where Chroma + SQLite + uploads live (Docker sets `/data`). |

## Project structure

```
learning-langchain/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app + static serving
│   │   ├── config.py          settings (.env)
│   │   ├── db.py              SQLite (conversations, messages, documents)
│   │   ├── rag.py            LangChain: ingest + retrieve + stream
│   │   ├── schemas.py
│   │   └── routers/           chat · documents · conversations
│   ├── tests/test_smoke.py
│   └── requirements.txt
├── frontend/                  Vite + React (SSE chat client)
├── Dockerfile · docker-compose.yml
├── list_models.py             provider model-discovery tool
└── DEFINITION_OF_DONE.md
```

## Tests

```bash
cd backend && pytest          # smoke tests (no network/key needed)
```

## Helper script

[`list_models.py`](list_models.py) lists models available for LangChain per provider (Fireworks, Anthropic, OpenAI, Google, Ollama). Auto-loads `.env`:
```bash
python3 list_models.py --provider fireworks
```

## Learning goals & related notes

This build exercises the core LangChain RAG path: chat models, prompts, document
loaders, chunking, embeddings, vector stores, retrieval, and streaming generation.
Connects to my notes on [RAG](../../topics/rag.md), [Chunking](../../topics/chunking.md),
[Embeddings](../../topics/embeddings.md), [Vector DBs](../../topics/vector-dbs.md),
[Retrieval Process](../../topics/retrieval-process.md), and [Generation](../../topics/generation.md).

**Possible next steps:** conversation memory tuning, reranking, LangGraph agent, LangSmith tracing.

## Notes / sources

-
