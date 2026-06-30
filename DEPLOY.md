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
EMBED_ORIGINS=["https://pyrotheum1702.com","https://www.pyrotheum1702.com"]
# optional but recommended for public exposure:
TAVILY_API_KEY=tvly_xxxxxxxx      # reliable web_search
RATE_LIMIT_PER_MINUTE=30          # tighten/loosen per expected traffic
```
`EMBED_ORIGINS` is what allows your website to iframe the bot — list the **parent
page** origins (your site), not the bot's own subdomain.

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

## Before you go fully public (recommended)
Per [NEXT_STEPS.md](NEXT_STEPS.md): add a **hard daily cost cap**, make sessions
**ephemeral**, and **remove the visitor-facing upload** so anonymous users can't write
to the knowledge base or run up the Fireworks bill. See [SECURITY.md](SECURITY.md).
