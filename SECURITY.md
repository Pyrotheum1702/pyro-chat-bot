# Security

Proportionate hardening for a **local / self-hosted learning app**. This is not a
multi-tenant production service — there's no auth (see Out of scope). The controls
below reduce the most realistic risks for an app that ingests user files and calls
a paid LLM.

## Threat model (what we actually worry about)

| Risk | Why it matters here |
|------|---------------------|
| Path traversal on upload | Filenames are attacker-controlled; a bad name could write outside the upload dir |
| Giant-file / flood DoS | Uploads and LLM calls are expensive (memory, tokens, $$) |
| Prompt injection via documents | Retrieved chunks are fed to the LLM; a document can contain "ignore your instructions…" |
| Information leakage | Stack traces / internal paths leaking to the client |
| XSS / clickjacking | The backend serves the built SPA |
| SQL injection | User text flows into the database |

## Implemented controls

**File upload** ([`routers/documents.py`](backend/app/routers/documents.py), [`security.py`](backend/app/security.py))
- **Filename sanitization** — `safe_filename()` reduces the upload name to a safe basename (strips `../`, absolute paths, odd characters), and `ensure_within()` re-checks the resolved path stays inside the upload directory.
- **Extension allow-list** — only `.pdf` / `.txt` / `.md`.
- **Size limit** — streamed to disk with a hard cap (`MAX_UPLOAD_MB`, default 20 MB); partial files are deleted on rejection.

**Chat / LLM** ([`routers/chat.py`](backend/app/routers/chat.py), [`rag.py`](backend/app/rag.py))
- **Message length limit** — `MAX_MESSAGE_CHARS` (default 8000) bounds token cost and abuse; empty messages rejected.
- **Prompt-injection guard** — the system prompt instructs the model to treat retrieved context as untrusted *data*, never as instructions. (Mitigation, not a guarantee — injection isn't fully solvable by prompting.)

**Rate limiting** ([`security.py`](backend/app/security.py))
- In-memory, per-client-IP fixed window on `/api/chat` and `/api/documents` (`RATE_LIMIT_PER_MINUTE`, default 30). Disable with `RATE_LIMIT_ENABLED=false`.

**Transport / headers** ([`main.py`](backend/app/main.py))
- Security headers on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, a restrictive `Content-Security-Policy` (`frame-ancestors 'none'`, `object-src 'none'`), `Referrer-Policy`, `Permissions-Policy`.
- **CORS** scoped to the known frontend origin(s) and only the methods/headers used — not a wildcard.

**Data layer** ([`db.py`](backend/app/db.py))
- All SQL uses **parameterized queries** — no string interpolation.

**Error handling**
- Internal exceptions are **logged server-side** and surfaced to the client as **generic messages** (no stack traces / paths).

**Secrets**
- API keys come from `.env` (gitignored, with `!.env.example` so only the template is committed); never hardcoded, never logged, never copied into the Docker image (passed as env vars).

## Configuration

All tunable via `.env` (see [.env.example](.env.example)):

| Var | Default | Purpose |
|-----|---------|---------|
| `MAX_UPLOAD_MB` | 20 | Upload size cap |
| `MAX_MESSAGE_CHARS` | 8000 | Chat message length cap |
| `RATE_LIMIT_ENABLED` | true | Toggle rate limiting |
| `RATE_LIMIT_PER_MINUTE` | 30 | Requests/min per IP on chat + upload |

## Out of scope (v1) — add before exposing publicly

- **Authentication / authorization** — anyone who can reach the port can use it. Put it behind auth (or a VPN) before exposing it.
- **TLS** — run behind a reverse proxy (Caddy/nginx/Traefik) terminating HTTPS.
- **Distributed rate limiting** — the in-memory limiter is per-process; use Redis (e.g. `slowapi`) behind multiple workers.
- **Malware / content scanning** of uploads.
- **Per-user data isolation** — all conversations/documents are shared.
- **Audit logging, secrets manager, dependency scanning** (e.g. `pip-audit`).

## Reporting

This is a personal learning project — open an issue if you spot something.
