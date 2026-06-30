# 🔥 PyroBot

> **PyroBot** — an AI assistant that knows me, embedded on
> [pyrotheum1702.com](https://pyrotheum1702.com). Ask it about my work, experience,
> and projects and it answers in real time, grounded in a curated knowledge base.

Built by **Nguyen Quang Duoc (Pyro)** — a full-stack game & systems engineer — both
as a live "talk to me" widget for visitors and as a demonstration of production
AI-engineering: agentic RAG, tool use, streaming, and security hardening.

---

## What it is

A single, seamless chat backed by a **tool-using agent (agentic RAG)** — no mode
toggle. The model decides what to do per message and grounds every answer about Pyro
in retrieved knowledge instead of guessing:

| Tool | What it does |
|------|--------------|
| **`search_documents`** | Semantic search over the "About Me" knowledge pack — the system prompt forces the agent to ground every answer about Pyro in retrieved content. |
| **`web_search`** | Public web search (Tavily if `TAVILY_API_KEY` is set, else a keyless DuckDuckGo fallback). |
| **`calculator`** | Safe arithmetic (AST-evaluated — no `eval`). |
| **`ingest_url`** | Fetch a web page and add it to the knowledge base. *(Withheld unless `ALLOW_PUBLIC_UPLOAD=true` — the KB is read-only to visitors by default.)* |

Responses **stream** token-by-token over SSE, and each tool call is surfaced in the
UI. Conversations and the vector store **persist** across restarts. The knowledge
pack in [`backend/knowledge/`](backend/knowledge/) is **auto-seeded** into the vector
store on first startup. Only read-only / additive tools are exposed — see
[SECURITY.md](SECURITY.md).

## Architecture

```
React SPA (Vite)                         dev :5173  ·  prod: served by backend
  │  POST /api/chat (SSE stream) · POST/GET /api/documents · GET /api/conversations
  ▼
FastAPI backend (:8017)
  ├─ Agent loop (LangChain): model ⇄ tools (search_documents · web_search ·
  │                          calculator · ingest_url) ─▶ Fireworks LLM ─▶ stream
  ├─ Vector store: load ─▶ chunk ─▶ embed (Fireworks) ─▶ Chroma   (+ startup seed)
  └─ SQLite   (conversations + messages)
```

> **Integrating PyroBot into a site or app?** See **[INTEGRATION.md](INTEGRATION.md)** —
> the HTTP/SSE API reference, client examples, and how to embed it.

## Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI + Uvicorn |
| Agent / RAG | LangChain (`langchain-fireworks`, `langchain-chroma`, text splitters, community loaders) |
| LLM | Fireworks — `accounts/fireworks/models/kimi-k2p6` (configurable) |
| Embeddings | Fireworks — `nomic-ai/nomic-embed-text-v1.5` |
| Vector store | Chroma (persisted to disk) |
| History | SQLite |
| Frontend | React (Vite), SSE streaming client |
| Packaging | Single Docker image (FastAPI serves the built React app) |

## Quickstart — local dev (two terminals)

Prereqs: Python 3.9+ and Node 18+, plus a **Fireworks API key**.

**1. Backend** (auto-loads `.env` for the key):
```bash
cp .env.example .env        # then fill in FIREWORKS_API_KEY
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

Open **http://localhost:5173** and ask *"Who is Pyro?"* — the first boot seeds the
knowledge pack via Fireworks embeddings, then answers should cite a
`search_documents` tool call.

## Run with Docker (single container)

```bash
# from this folder, with .env present (containing FIREWORKS_API_KEY)
docker compose up --build
```
Open **http://localhost:8017**. Chroma + SQLite persist in the `ragdata` volume.

## Deploy & embed on a website

To run it on a VPS behind HTTPS and embed it as a floating iframe on your site, see
**[DEPLOY.md](DEPLOY.md)** — Docker + Caddy (auto-TLS) stack in [`deploy/`](deploy/),
plus the `EMBED_ORIGINS` setting and the iframe snippet.

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
| `TAVILY_API_KEY` | — | Optional. Enables reliable `web_search`. |
| `DAILY_COST_CAP_USD` | `1.0` | Hard daily spend cap (USD, UTC day) on chat; `0` disables. Returns `429` once hit. |
| `USD_PER_MILLION_INPUT_TOKENS` / `…OUTPUT…` | `0.9` / `0.9` | Price estimate used to meter the cap — tune to your model. |
| `RATE_LIMIT_PER_MINUTE` | `30` | Requests/min per IP on chat + upload. |
| `ALLOW_PUBLIC_UPLOAD` | `false` | When off, the KB is read-only to visitors: `POST /api/documents` → 403 and `ingest_url` is withheld. |
| `CORS_ORIGINS` | `localhost:5173` | JSON list of origins allowed to call the API cross-origin. |
| `EMBED_ORIGINS` | `[]` | JSON list of origins allowed to `<iframe>` the app (e.g. your site). Empty = framing blocked. |
| `DATA_DIR` | `backend/data` | Where Chroma + SQLite live (Docker sets `/data`). |

## The knowledge base

The bot's facts about Pyro live in [`backend/knowledge/`](backend/knowledge/) as
plain Markdown (`about`, `experience`, `projects`, `skills`, `honors`, `faq`),
curated from my CV. Editing those files and restarting re-seeds the vector store —
that's how I keep the bot accurate. Personal source docs (CV, etc.) are gitignored
and never committed.

## Data & secrets

Nothing sensitive or environment-specific lives in git — it's provisioned or
regenerated per environment. This matters when you clone elsewhere (e.g. the VPS):

| Artifact | In git? | How a fresh clone gets it |
|----------|---------|---------------------------|
| `.env` (API keys) | ❌ gitignored | `cp .env.example .env`, fill `FIREWORKS_API_KEY` (+ optional `TAVILY_API_KEY`) — per environment |
| `*-CV.pdf` (personal source doc) | ❌ gitignored | Not needed — see below |
| `backend/knowledge/*.md` (the facts) | ✅ committed | Travels automatically |
| `backend/data/chroma` (vector store) | ❌ gitignored | **Rebuilt on first boot** from the knowledge pack |
| `backend/data/*.sqlite` (chat history) | ❌ gitignored | Starts empty; local to each deployment |

- **Secrets are per-environment.** Each place you run PyroBot needs its own `.env`; the
  Fireworks key is never committed and never sent to the browser. The CV is only *source
  material* — the bot's knowledge is the committed `knowledge/*.md` pack, so a clone fully
  "knows about Pyro" without it.
- **The vector store is reproducible.** On first boot, `seed_knowledge()` ingests
  `knowledge/*.md` into a fresh Chroma store and writes a `.seeded` sentinel so it only
  happens once (a small one-time Fireworks embedding cost per environment).
- **To update what the bot knows:** edit `knowledge/*.md`, delete `backend/data/.seeded`
  (or the whole `data/` dir), and restart to re-seed. Editing the CV alone does nothing.
- **`backend/data/` is not backed up by git.** To preserve real conversation history or a
  curated vector store, back up that directory (or the Docker `ragdata` volume) separately.

## Security

Public-facing hardening is part of the demo: path-traversal-safe uploads, rate
limiting, security headers, scoped CORS, a prompt-injection guard, an SSRF guard on
`ingest_url`, and a no-`eval` calculator. Details in [SECURITY.md](SECURITY.md).

## Project structure

```
pyro-chat-bot/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app + static serving + knowledge seeding
│   │   ├── agent.py           tool-using agent loop (streaming)
│   │   ├── tools.py           search_documents · web_search · calculator · ingest_url
│   │   ├── rag.py             ingest + retrieve + Chroma vector store
│   │   ├── config.py          settings (.env)
│   │   ├── db.py              SQLite (conversations, messages, documents)
│   │   ├── security.py        rate limit · headers · filename/path guards
│   │   ├── schemas.py
│   │   └── routers/           chat · documents · conversations
│   ├── knowledge/             the "About Me" pack (auto-seeded)
│   ├── tests/test_smoke.py
│   └── requirements.txt
├── frontend/                  Vite + React (SSE chat client)
├── Dockerfile · docker-compose.yml
├── list_models.py             provider model-discovery helper
├── INTEGRATION.md             API reference + how to embed PyroBot
├── DEPLOY.md · deploy/        VPS deploy (Docker + Caddy) + website embed
├── DEFINITION_OF_DONE.md · SECURITY.md · NEXT_STEPS.md
```

## Tests

```bash
cd backend && pytest          # smoke tests (no network/key needed)
```

## Roadmap

This bot is being shaped into a public, embeddable widget for my site. The full plan
— public-shaping (ephemeral sessions, cost cap), the floating widget, and VPS deploy
— lives in [NEXT_STEPS.md](NEXT_STEPS.md).

## About Pyro

Full-stack game & systems engineer based in Ha Noi, Vietnam (~5 years) — real-time
multiplayer, blockchain/Web3 gaming, and Telegram Mini Apps.
[Website](https://pyrotheum1702.com) · [GitHub](https://github.com/Pyrotheum1702) ·
[X](https://x.com/pyro1702)

## License

Code under [MIT](LICENSE).
