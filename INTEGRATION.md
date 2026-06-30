# PyroBot — Integration Guide

How to talk to the PyroBot backend, and how to embed it on a website
(e.g. [pyrotheum1702.com](https://pyrotheum1702.com)).

There are two integration paths:

1. **Use the HTTP API directly** — drive the chat from your own frontend (React,
   plain JS, mobile, server-to-server). This is the supported, stable path today.
2. **Embed the chat UI** — drop the bot onto a page as an iframe or floating widget.
   Today this needs two header/CORS changes (below); a one-line widget snippet is on
   the [roadmap](NEXT_STEPS.md).

---

## 1. API reference

### Base URL & origin model
- **Dev:** backend on `http://localhost:8017`; the Vite dev server (`:5173`) proxies
  `/api/*` to it, so the SPA calls **same-origin** (`BASE = ""`).
- **Prod:** the backend serves the built SPA, so the UI and API share one origin
  (e.g. `https://chat.pyrotheum1702.com`). All paths below are relative to that origin.

### Authentication
None today — the bot is a public, read-only assistant. Protection comes from rate
limiting, input caps, and (in production) origin scoping. Don't expose write/admin
operations publicly; keep document ingestion on a private path (see
[Production notes](#5-production-notes)).

### CORS
The API only honors cross-origin browser requests from `cors_origins`
(default `http://localhost:5173`, `http://127.0.0.1:5173`). To call the API from
your site's origin, add it via the `CORS_ORIGINS` env var:

```bash
CORS_ORIGINS=["https://pyrotheum1702.com","https://www.pyrotheum1702.com"]
```

Allowed methods: `GET, POST, OPTIONS`. Allowed request header: `Content-Type`.

### Rate limits & input caps
| Limit | Default | Applies to | On exceed |
|-------|---------|-----------|-----------|
| Requests / IP / minute | `30` | `/api/chat`, `/api/documents` | `429` |
| **Daily cost cap** | **`$1.00`** | `/api/chat` | `429` until next UTC day |
| Message length | `8000` chars | `/api/chat` | `413` |
| Upload size | `20` MB | `/api/documents` | `413` |
| Agent tool steps / turn | `6` | `/api/chat` | stream ends with a "stopped" note |

All are configurable via env (`RATE_LIMIT_PER_MINUTE`, `DAILY_COST_CAP_USD`,
`MAX_MESSAGE_CHARS`, `MAX_UPLOAD_MB`, `AGENT_MAX_STEPS`). Rate limiting is in-memory per
IP (fixed window); behind a reverse proxy, forward the real client IP.

**Daily cost cap.** A hard kill-switch: each chat turn's spend is estimated from token
counts and accumulated per UTC day. Once `DAILY_COST_CAP_USD` (default `1.0`; `0`
disables) is reached, `/api/chat` returns `429` with
`"…reached its daily usage limit…"` until the next day. `GET /api/health` reports
`daily_cost_cap_usd` and `spent_today_usd`. The estimate uses
`USD_PER_MILLION_INPUT_TOKENS` / `USD_PER_MILLION_OUTPUT_TOKENS` — tune them to your
model so the cap reflects real cost.

---

### `POST /api/chat` — streaming chat (SSE)

The core endpoint. Send a message, receive a **Server-Sent Events** stream of tokens
and tool activity. The full assistant answer is persisted server-side when the stream
completes.

**Request body** (`application/json`):
```json
{
  "message": "Who is Pyro and what does he build?",
  "conversation_id": null
}
```
- `message` *(string, required)* — the user's message.
- `conversation_id` *(int | null)* — omit/`null` to start a new conversation; the id
  is returned in the first `start` event. Pass it back to continue the thread.

**Response:** `Content-Type: text/event-stream`. Each event is a `data:` line with a
JSON payload, separated by a blank line:

```
data: {"type":"start","conversation_id":42}

data: {"type":"tool","name":"search_documents","input":{"query":"who is Pyro"}}

data: {"type":"tool_result","name":"search_documents","output":"# About Pyro ..."}

data: {"type":"token","value":"Pyro"}

data: {"type":"token","value":" is a full-stack"}

data: {"type":"done"}
```

**Event types:**

| `type` | Fields | Meaning |
|--------|--------|---------|
| `start` | `conversation_id` | Stream opened; capture the id for follow-ups. |
| `tool` | `name`, `input` | The agent is calling a tool. |
| `tool_result` | `name`, `output` (truncated ~600 chars) | The tool returned. |
| `token` | `value` | A chunk of the answer — concatenate in arrival order. |
| `sources` | `sources[]` (`source`, `page`, `snippet`) | Retrieval citations, when emitted. |
| `error` | `message` | Generation failed; a generic, safe message. |
| `done` | — | Stream finished (always sent last). |

Build the final answer by concatenating every `token.value`. Treat `tool`/`tool_result`
as optional UI affordances ("🔍 searching documents…").

**Note:** browsers' native `EventSource` only does `GET`, so use `fetch` + a
`ReadableStream` reader (this endpoint is `POST`). See the example below.

---

### Conversations

| Method & path | Body | Returns |
|---------------|------|---------|
| `GET /api/conversations` | — | `[{id, title, created_at}, ...]` (newest first) |
| `POST /api/conversations` | `{"title": "..."}` (optional) | the created conversation |
| `GET /api/conversations/{id}` | — | `{conversation, messages: [{id, role, content, created_at}]}` |

Not rate-limited. For a public, multi-visitor deployment you'll likely make sessions
**ephemeral** and drop the shared list (see [roadmap](NEXT_STEPS.md)).

### Documents (knowledge base)

| Method & path | Body | Returns |
|---------------|------|---------|
| `POST /api/documents` | `multipart/form-data`, field `file` | `{id, filename, chunks, created_at}` |
| `GET /api/documents` | — | list of ingested documents |

`POST` accepts `.pdf`, `.txt`, `.md`, ≤ 20 MB; the file is chunked, embedded, and
added to the vector store. **Keep this off the public surface** — gate it behind auth
or a private network path so visitors can't write to the knowledge base.

---

## 2. Client examples

### Streaming chat — vanilla JS (browser)
```js
async function streamChat({ message, conversationId }, handlers) {
  const res = await fetch("https://chat.pyrotheum1702.com/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId ?? null }),
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const line = block.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const ev = JSON.parse(line.slice(5).trim());

      if (ev.type === "start")        handlers.onStart?.(ev.conversation_id);
      else if (ev.type === "token")   handlers.onToken?.(ev.value);
      else if (ev.type === "tool")    handlers.onTool?.(ev);
      else if (ev.type === "error")   handlers.onError?.(ev.message);
      else if (ev.type === "done")    handlers.onDone?.();
    }
  }
}

// Usage
let answer = "";
streamChat({ message: "What has Pyro shipped?" }, {
  onStart: (id) => (window.convId = id),
  onToken: (t) => { answer += t; render(answer); },
  onError: (m) => console.error(m),
  onDone: () => console.log("done"),
});
```
(The shipped frontend's reference implementation lives in
[`frontend/src/api.js`](frontend/src/api.js).)

### Quick check — curl
```bash
curl -N -X POST https://chat.pyrotheum1702.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Who is Pyro?"}'
```
`-N` disables buffering so you see tokens arrive live.

### Server-to-server (Python)
```python
import json, httpx

with httpx.stream("POST", "https://chat.pyrotheum1702.com/api/chat",
                  json={"message": "Who is Pyro?"}, timeout=None) as r:
    for line in r.iter_lines():
        if line.startswith("data:"):
            ev = json.loads(line[5:].strip())
            if ev["type"] == "token":
                print(ev["value"], end="", flush=True)
```

---

## 3. Embedding on your website

### iframe (the supported embed path)
By default the backend **blocks framing** (`X-Frame-Options: DENY` + CSP
`frame-ancestors 'none'`). To let your site embed it, set **`EMBED_ORIGINS`** to the
**parent page's** origin(s) — no code change:

```bash
EMBED_ORIGINS=["https://pyrotheum1702.com","https://www.pyrotheum1702.com"]
```

When set, the backend emits `frame-ancestors 'self' <your origins>` and drops
`X-Frame-Options` (which has no per-origin allow-list). Leave it unset to stay locked.

**No CORS change needed** for this path: the iframe loads the SPA from the backend's
own origin (`chat.pyrotheum1702.com`), so its `/api` calls are **same-origin**. CORS
only matters if a page calls the API *directly* (cross-origin) — see [CORS](#cors).

Then drop this onto your site (e.g. in the Next.js layout):
```html
<iframe
  src="https://chat.pyrotheum1702.com"
  title="PyroBot"
  style="position:fixed;bottom:24px;right:24px;width:380px;height:560px;
         border:0;border-radius:16px;box-shadow:0 8px 30px rgba(0,0,0,.25);z-index:9999"
  allow="clipboard-write">
</iframe>
```
Full server setup is in [DEPLOY.md](DEPLOY.md).

### Planned: one-line floating widget
A self-contained bubble + panel injected by a small script — no iframe, no CORS dance
for the host page:
```html
<script src="https://chat.pyrotheum1702.com/widget.js" defer></script>
```
This is roadmap item #4 in [NEXT_STEPS.md](NEXT_STEPS.md); the snippet above is the
intended shape, not yet shipped.

---

## 4. Errors

Errors are JSON `{"detail": "..."}` with a standard status code — **except** failures
*during* a chat stream, which arrive as an in-stream `{"type":"error"}` event (the
HTTP status is already `200` by then).

| Status | When |
|--------|------|
| `400` | Empty message · unsupported upload type · unextractable file |
| `404` | Unknown conversation id |
| `413` | Message too long · upload too large |
| `429` | Rate limit exceeded · or the daily cost cap is reached |
| `500` | Internal failure (details are logged server-side, never leaked) |

---

## 5. Production notes
- **Lock origins.** Set `CORS_ORIGINS` (and the CSP `frame-ancestors`) to your exact
  domains — never `*`.
- **Terminate TLS** at a reverse proxy (Caddy/NGINX) and forward the real client IP so
  per-IP rate limiting works.
- **Keep writes private.** `POST /api/documents` and `ingest_url` mutate the knowledge
  base — don't expose them to anonymous visitors.
- **Cap cost.** Add a hard daily request/token ceiling before going public (roadmap #3)
  so a traffic spike can't drain the Fireworks budget.
- **Server-side key.** `FIREWORKS_API_KEY` lives only in the backend env; it is never
  sent to the browser.

See [SECURITY.md](SECURITY.md) for the full threat model and [README.md](README.md)
for setup.
