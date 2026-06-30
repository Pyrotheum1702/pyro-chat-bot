# PyroBot — VPS Deploy & Website Embed

Deploy PyroBot to your VPS behind HTTPS, then embed it on
[pyrotheum1702.com](https://pyrotheum1702.com) as a floating iframe.

The deploy stack lives in [`deploy/`](deploy/): a production `docker-compose.yml`
(app + Caddy) and a `Caddyfile`. Caddy terminates TLS (auto Let's Encrypt) and
reverse-proxies to the app over the internal Docker network — the app itself is never
published to the host.

```
Browser ──HTTPS──▶ Caddy (:443, auto-TLS) ──http──▶ app:8017 (FastAPI + SPA)
```

## 0. Prerequisites
- A VPS with **Docker + Docker Compose** and ports **80 + 443** open.
- A **subdomain** for the bot, e.g. `chat.pyrotheum1702.com`, with a **DNS A record**
  pointing at the VPS public IP. (Keep it on a subdomain so it's isolated from the
  main site.)
- Your **Fireworks API key**.

## 1. Point DNS
Create an `A` record: `chat.pyrotheum1702.com → <VPS_IP>`. Verify it resolves before
deploying (Caddy needs it to issue the certificate):
```bash
dig +short chat.pyrotheum1702.com      # should print your VPS IP
```

## 2. Get the code on the VPS
```bash
git clone https://github.com/Pyrotheum1702/pyro-chat-bot.git
cd pyro-chat-bot
```

## 3. Create `.env`
```bash
cp .env.example .env
```
Edit `.env` and set at least:
```bash
FIREWORKS_API_KEY=fw_xxxxxxxx
# Native embed (site calls /api/chat cross-origin) → allow the site's origins:
CORS_ORIGINS=["https://pyrotheum1702.com","https://www.pyrotheum1702.com"]
# Only needed if you instead embed via <iframe>:
EMBED_ORIGINS=["https://pyrotheum1702.com","https://www.pyrotheum1702.com"]
# optional but recommended for public exposure:
TAVILY_API_KEY=tvly_xxxxxxxx      # reliable web_search
RATE_LIMIT_PER_MINUTE=30          # tighten/loosen per expected traffic
DAILY_COST_CAP_USD=1.0            # raise to your budget (a global cap → 429s everyone once hit)
```
Pick the embed that matches your site:
- **Native** (site renders the chat UI, calls the API directly) → set **`CORS_ORIGINS`**.
- **iframe** (site frames the bot's own page) → set **`EMBED_ORIGINS`**; CORS isn't needed.

Leave `EXPOSE_CONVERSATIONS` and `ALLOW_PUBLIC_UPLOAD` unset (off) for a public site.
`TRUST_PROXY_HEADERS=true` is already set in `deploy/docker-compose.yml` (you're behind
Caddy), so per-IP rate limiting uses the real client IP.

## 4. Set your hostname
Edit [`deploy/Caddyfile`](deploy/Caddyfile) and replace `chat.pyrotheum1702.com` with
your actual subdomain (must match the DNS record from step 1).

## 5. Launch
```bash
cd deploy
docker compose up -d --build
```
First boot: the app seeds the knowledge pack into Chroma (one-time Fireworks embedding
call), and Caddy fetches a TLS cert. Watch it come up:
```bash
docker compose logs -f          # look for the app "seeded N chunks" line + Caddy cert
```
Then open **https://chat.pyrotheum1702.com** and ask *"Who is Pyro?"* — you should get a
grounded answer with a `search_documents` tool call.

## 6. Embed on the website
Add this to your Next.js site (e.g. in the root `layout.tsx`, outside `<main>`):
```html
<iframe
  src="https://chat.pyrotheum1702.com"
  title="Chat with Pyro"
  style="position:fixed;bottom:24px;right:24px;width:380px;height:560px;
         border:0;border-radius:16px;box-shadow:0 8px 30px rgba(0,0,0,.25);z-index:9999"
  allow="clipboard-write">
</iframe>
```
Because the iframe loads the SPA from the bot's own origin, its `/api` calls are
same-origin — **no CORS setup needed**. The only requirement is that your site's origin
is in `EMBED_ORIGINS` (step 3), which the backend turns into a CSP
`frame-ancestors` allowance.

> **Nicer UX (optional):** instead of a permanently-visible 380×560 iframe, render your
> own small "Chat with Pyro 🔥" button on the site and toggle the iframe's visibility on
> click. The iframe stays the same; only the host page adds a button + show/hide.

## 7. Operations
```bash
# update to the latest code
git pull && cd deploy && docker compose up -d --build

# logs / restart / stop
docker compose logs -f app
docker compose restart app
docker compose down            # stop (keeps volumes/data)

# refresh what the bot knows: edit backend/knowledge/*.md, then re-seed
docker compose exec app rm -f /data/.seeded && docker compose restart app
```

**Backups:** chat history + vector store live in the `ragdata` Docker volume (not in
git). Back it up if you want to keep them:
```bash
docker run --rm -v deploy_ragdata:/data -v "$PWD":/backup alpine \
  tar czf /backup/ragdata-backup.tgz -C /data .
```

## Cost cap
A hard **daily spend cap** is built in — `DAILY_COST_CAP_USD` (default **$1.00/UTC
day**). Once the day's estimated spend is reached, chat returns `429` until the next
day, so a traffic spike can't drain the Fireworks bill. Tune it (and the per-token
price estimates) in `.env`; check `GET /api/health` for `spent_today_usd`. See
[SECURITY.md](SECURITY.md).

## Before you go fully public (recommended)
The **cost cap** and a **read-only knowledge base** are already in place — public upload
is off by default (`ALLOW_PUBLIC_UPLOAD=false`: `POST /api/documents` → 403, `ingest_url`
withheld), so visitors can't write to the KB or run up the bill. Update the KB privately
by editing `backend/knowledge/*.md` and re-seeding (see step 7).

Still on the list per [NEXT_STEPS.md](NEXT_STEPS.md): make per-visitor sessions
**ephemeral** (drop the shared conversation sidebar) before high-traffic exposure.
