# PyroBot — Knowledge Base & Document Ingestion

How the bot gets its facts, and how to add or update documents — locally and on prod.

PyroBot answers from a **vector store** (Chroma). At query time the agent's
`search_documents` tool retrieves the most relevant chunks and grounds its reply in
them. Everything in that store comes from **one source of truth**: the committed
knowledge pack in [`backend/knowledge/`](backend/knowledge/).

```
backend/knowledge/*.md  ──seed──▶  chunk → embed (Fireworks) → Chroma  ──search_documents──▶  agent
```

## TL;DR

| You want to… | Do this |
|--------------|---------|
| Add/edit a fact | Edit a file in `backend/knowledge/`, commit, deploy, **re-seed** |
| Add a whole document | Drop a `.md` / `.txt` / `.pdf` into `backend/knowledge/`, commit, deploy, **re-seed** |
| Re-seed (prod) | `docker compose exec app rm -f /data/.seeded && docker compose restart app` |
| Upload a file to the live API | **Not supported on prod** — disabled by design (see below) |

## What can be ingested

The seeder and the upload path accept three file types ([`rag.py`](backend/app/rag.py)):

| Type | Loader | Notes |
|------|--------|-------|
| `.md` | text | The knowledge pack today |
| `.txt` | text | Plain text |
| `.pdf` | `PyPDFLoader` | Extracted text only — no OCR for scanned images |

Anything else in `knowledge/` is skipped, and `README.md` is treated as meta (not
ingested). Files are chunked (`CHUNK_SIZE=1000`, `CHUNK_OVERLAP=150`) before embedding.

## How seeding works

On startup the app runs `seed_knowledge()` ([`rag.py`](backend/app/rag.py)):

1. If `<DATA_DIR>/.seeded` exists → **skip** (so normal restarts don't re-embed).
2. Otherwise → **clear** the vector store + document records, then ingest every
   supported file in `knowledge/`, and write the `.seeded` sentinel.

Because step 2 clears first, **re-seeding is idempotent** — running it repeatedly
rebuilds the store from scratch and never duplicates content. The sentinel is only
written if something actually landed, so a missing `FIREWORKS_API_KEY` (which makes
embedding fail) won't lock you into an empty store.

> The embedding cost is one-time per environment (≈13 chunks for the default pack).
> A re-seed re-embeds the whole pack, so it costs that again — negligible, but not free.

## Updating the knowledge base

### 1. Edit locally
Edit or add files under `backend/knowledge/`. Keep facts accurate and reconciled
against the CV (**the CV wins**), and **never include secrets** — the phone number from
the CV must not appear here. Both repos are public.

### 2. Ship it (two-repo mirror)
```bash
git add projects/learning-langchain/backend/knowledge/
git commit -m "KB: <what changed>"
git push origin main
git subtree push --prefix=projects/learning-langchain pyro-chat-bot main
```

### 3. Deploy + re-seed on the VPS
```bash
cd ~/pyro-chat-bot && git pull
cd deploy
docker compose exec app rm -f /data/.seeded && docker compose restart app
docker compose logs -f app          # watch for "seeded N chunks from the knowledge pack"
```

### 4. Verify
```bash
curl -N -X POST https://chat.pyrotheum1702.com/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"<ask something only the new content answers>"}'
```

## Local development

Same idea without Docker — delete the sentinel and restart the backend:
```bash
rm -f backend/data/.seeded
# restart uvicorn; on boot it re-seeds from backend/knowledge/
```
Editing the CV alone does nothing — only `knowledge/*.md` feeds the bot.

## Why the upload endpoint is disabled on prod

`POST /api/documents` exists but is gated behind `ALLOW_PUBLIC_UPLOAD`, which is
**`false`** in prod → it returns **403**. There's no per-user auth, so enabling it would
open writes to *everyone*, letting visitors poison the knowledge base or run up the
embedding bill. The deliberate trade-off: the KB is **read-only** in public, curated
privately through `knowledge/` + re-seed.

For a **private/dev** instance you can flip it on:
```bash
ALLOW_PUBLIC_UPLOAD=true     # POST /api/documents now accepts .md/.txt/.pdf (≤ MAX_UPLOAD_MB)
```
Uploads land in the same vector store. Note a later re-seed **clears** them (it rebuilds
from `knowledge/` only), so anything you want to keep belongs in `knowledge/`.

## Caveats

- **Re-seed clears everything**, including runtime uploads — `knowledge/` is the only
  durable source. This is intended for the public deployment.
- **Vectors aren't backed up by git** — `backend/data/` (Chroma + SQLite) is gitignored
  and rebuilt from the pack. Back up the `ragdata` volume if you want to keep chat
  history (see [DEPLOY.md](DEPLOY.md) → Operations).
- **PDF = text extraction only.** Scanned/image PDFs ingest as little or no text.
- **Don't `rm -rf backend/data`** — that nukes live conversations too. To rebuild only
  the vectors, deleting `.seeded` and restarting is enough (the seeder clears the
  collection for you).

## Related docs

- [DEPLOY.md](DEPLOY.md) — VPS deploy, operations, backups
- [INTEGRATION.md](INTEGRATION.md) — API surface (`/api/chat`, `/api/documents`) and limits
- [SECURITY.md](SECURITY.md) — public-exposure posture, the read-only-KB decision
