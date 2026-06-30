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
- ✅ **No cross-visitor leak** — DONE: `EXPOSE_CONVERSATIONS=false` (default) unmounts the
  conversation list/detail endpoints; chat continuity uses the `conversation_id` from
  `/api/chat`. Unmatched `/api/*` now 404s (SPA catch-all no longer serves API routes).
  `TRUST_PROXY_HEADERS` added for correct per-IP limiting behind Caddy.
- Optional further step: fully **ephemeral sessions** (don't persist visitor chats at all).

### 4. Embed on the website  — site shipped NATIVE
The site (pyrotheum1702.com) integrated in **native** mode: it renders its own chat UI
and calls `POST /api/chat` cross-origin (so `CORS_ORIGINS` must include the site).
Backend supports both this and the iframe path (`EMBED_ORIGINS` → CSP frame-ancestors).
**Bumped priority — ship a drop-in `widget.js`** (per site-maintainer feedback): a
one-line `<script>` so future embeds don't re-implement the POST+ReadableStream SSE
parser. Reference client exists on the site side (`lib/pyrobot.ts` streamChat()).

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
