# Definition of Done — RAG Chatbot Web App

A LangChain-powered chatbot that answers questions grounded in documents the user
uploads (RAG), with a FastAPI backend and a React frontend.

## Locked decisions (from scoping)

| Decision | Choice |
|----------|--------|
| LLM provider | **Fireworks** (open models, OpenAI-compatible) |
| Capability | **RAG** over user-uploaded documents |
| Web stack | **FastAPI** (backend) + **React** (frontend SPA) |
| In scope (v1) | Streaming responses · Persistent chat history · Dockerfile + deploy notes |
| Out of scope (v1) | LangSmith tracing · Auth / multi-user · Tool-using agent · Production scaling |

## Assumed defaults (override if you disagree — see open questions)

| Area | Default |
|------|---------|
| Vector store | **Chroma**, persisted to disk |
| Embeddings | **Fireworks embeddings** (`nomic-ai/nomic-embed-text-v1.5`) — keeps it API-based/light |
| Chat model | A Fireworks chat model via env (e.g. `accounts/fireworks/models/kimi-k2p6`) |
| Document types | PDF, TXT, Markdown |
| Chat persistence | **SQLite** |
| Streaming transport | SSE (FastAPI → React) |

## Target architecture

```
React SPA (chat UI, upload, sources)
   │  POST /chat (SSE stream),  POST/GET /documents,  GET /conversations
   ▼
FastAPI backend
   ├─ RAG chain (LangChain): retrieve top-k ─▶ prompt ─▶ Fireworks LLM ─▶ stream
   ├─ Ingestion: load ─▶ chunk ─▶ embed (Fireworks) ─▶ Chroma
   ├─ Chroma  (vectors, on disk)
   └─ SQLite  (conversations + messages)
```

---

## Definition of Done — acceptance criteria

The project is **done** when every box below is checked and the end-to-end happy
path passes on a fresh clone.

### Document ingestion & retrieval
- [ ] User can upload a PDF / TXT / MD file from the UI.
- [ ] Uploaded docs are loaded, chunked, embedded, and stored in Chroma; the UI shows ingestion status (and surfaces errors).
- [ ] A query retrieves the top-k most relevant chunks (k configurable via env).
- [ ] Answers are grounded in retrieved context, and the UI shows which source chunks/citations were used.
- [ ] When no relevant context is found, the bot says it doesn't know instead of hallucinating.

### Backend (FastAPI)
- [ ] `POST /chat` takes a message + conversation id, runs the RAG chain, and streams the answer.
- [ ] `POST /documents` (upload) and `GET /documents` (list) work.
- [ ] `GET /conversations` and `GET /conversations/{id}` return history.
- [ ] All config (model id, embeddings model, API key, k, chunk size) comes from env/`.env`; no secrets in code.
- [ ] Errors return clean JSON with appropriate HTTP status codes.

### Streaming
- [ ] Assistant responses stream token-by-token to the UI (SSE).
- [ ] Mid-stream errors and client disconnects are handled gracefully (no hung requests).

### Persistence
- [ ] Chat history survives a server restart (SQLite).
- [ ] The vector store survives a restart (Chroma on disk) — no re-ingest needed.
- [ ] Past conversations can be listed and reopened.

### Frontend (React)
- [ ] Chat interface: message list, input box, send button.
- [ ] Streamed responses render incrementally as they arrive.
- [ ] Document upload UI with progress/status.
- [ ] Answer sources/citations are displayed.
- [ ] Conversation list + "new chat".
- [ ] Reasonable loading and error states.

### Quality / correctness
- [ ] End-to-end happy path: upload a doc → ask about it → get a grounded, streamed answer that persists after restart.
- [ ] Basic input validation (file type/size, empty message).
- [ ] At least a smoke test for the RAG chain and for `POST /chat`.
- [ ] "How to run" in the README verified from a fresh clone.

### Packaging & deploy
- [ ] Dockerfile(s) build the app; `docker compose up` runs backend + frontend together.
- [ ] Deploy notes: local run, required env vars, ports, and how to point at a target host.

### Docs
- [ ] README updated: architecture, setup, env vars, run, and deploy.
- [ ] `.env.example` lists every needed var (`FIREWORKS_API_KEY`, chat model, embeddings model, etc.).

---

## Non-goals (explicitly out for v1)
- Authentication / multi-user accounts
- LangSmith tracing
- Tool-using agent / function calling
- Rate limiting, horizontal scaling, production hardening

## Resolved sub-decisions
1. **Embeddings** — Fireworks `nomic-ai/nomic-embed-text-v1.5` (API-based, light). ✅
2. **Default chat model** — `accounts/fireworks/models/kimi-k2p6` (configurable via env). ✅
3. **Packaging** — single container: FastAPI serves the built React app. ✅
