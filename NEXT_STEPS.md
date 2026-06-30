# Next Steps — learning-langchain → portfolio "chat with me" bot

**Goal:** a public, embeddable "chat with me" chatbot on **pyrotheum1702.com** that
knows about Pyro (from a curated knowledge pack) and demonstrates AI-engineering
skill. See [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md) and the project memory.

## Current state (as of 2026-06-30)
Built and pushed to `origin/main`:
- **Agentic RAG**: single `/api/chat` endpoint runs a tool-using agent — tools:
  `search_documents`, `web_search`, `calculator`, `ingest_url`. No mode toggle.
- **Persona + grounding** prompt in `agent.py` (draft): grounds answers about Pyro
  via `search_documents`, never invents facts.
- **Knowledge pack** in `backend/knowledge/` (about, experience, projects, skills,
  honors, faq) — built from CV, reconciled vs. the website. Auto-seeded into Chroma
  on first startup (`rag.seed_knowledge()` + lifespan).
- Streaming (SSE), SQLite persistence, Chroma vector store, security hardening
  (upload limits, rate limit, headers, CORS, prompt-injection guard), single-container
  Docker, backend on **port 8017**.
- **Stack**: FastAPI + React (Vite) + LangChain + Fireworks (`kimi-k2p6`) + Chroma + SQLite.

## Priority order

### 1. Verify it works live  ⬅ DO FIRST (not yet done)
Run backend (first boot seeds the knowledge pack via Fireworks embeddings) + frontend,
ask "who is Pyro?", confirm a grounded answer + a `search_documents` tool call.
`uvicorn app.main:app --reload --port 8017 --app-dir backend` then `npm run dev` (5173).

### 2. Three open decisions (block features)
- **Current status / availability** — fixes "are you available?" (TODO in knowledge pack)
- **Book-a-call destination** — email to capture leads to, or Telegram/Calendly link → enables a `book_a_call` tool
- **Monthly budget + expected traffic** — sizes the daily cost cap + public model choice

### 3. Make it "public-shaped"
- ✅ **Cost guardrail** — DONE: hard daily spend cap (`DAILY_COST_CAP_USD`, default $1/UTC
  day) in `cost.py`; chat returns 429 once hit. See SECURITY.md / DEPLOY.md.
- ✅ **Read-only KB to visitors** — DONE: `ALLOW_PUBLIC_UPLOAD=false` by default disables
  `POST /api/documents` (403) and withholds `ingest_url`; upload UI removed from the SPA.
  Private path: edit `backend/knowledge/*.md` + re-seed.
- **Ephemeral per-visitor sessions** (drop the shared conversation sidebar) — still TODO

### 4. Embed on the website  — DECIDED: iframe
Floating `<iframe>` on pyrotheum1702.com (decided over a JS widget for speed — reuses
the existing SPA). Backend support is **done**: `EMBED_ORIGINS` env var drives the CSP
`frame-ancestors` allow-list. Snippet + setup in `DEPLOY.md`. Optional polish: a host-page
"Chat with Pyro" button that toggles the iframe instead of always showing it.

### 5. Deploy to the VPS  — runbook ready
Docker + Caddy (auto-HTTPS) stack in `deploy/` + `DEPLOY.md`. Remaining: point DNS
(`chat.pyrotheum1702.com` → VPS), set `.env` (`FIREWORKS_API_KEY`, `EMBED_ORIGINS`),
`docker compose up -d --build`. Do the public-shaping (#3) before opening it to traffic.

## Quick wins (anytime)
- Set **`TAVILY_API_KEY`** so `web_search` actually returns results (DuckDuckGo fallback can't
  run on the local macOS LibreSSL Python; works in Docker/OpenSSL but Tavily is the reliable path).
- Finalize **persona voice** — first-person ("Hi, I'm Pyro") vs. "Pyro's assistant".

## Open TODOs already in the knowledge pack
`backend/knowledge/`: availability, contact path, location, project links.
