# PyroBot — working agreement for Claude

Instructions for Claude Code when working in this project. These are standing rules —
the user should **not** have to remember to ask for them.

## Docs are part of the change (do this without being told)

When you change code, update the affected docs **in the same change**, then state in
your summary which docs you touched (or "no doc changes needed" and why). Treat a code
change with stale docs as incomplete.

Mapping — when you change… → update:

| Code / behavior change | Update |
|------------------------|--------|
| API endpoint, request/response shape, or an SSE event type | `INTEGRATION.md` |
| Config setting / env var (added, renamed, default changed) | `README.md` config table **and** `.env.example` **and** `INTEGRATION.md` limits table |
| A tool, the agent loop, the stack, or the architecture | `README.md` (tool table / architecture / stack) |
| Project status, scope, or what's done vs. next | `NEXT_STEPS.md` and the README status line |
| Security posture (headers, CORS, rate limits, auth, guards) | `SECURITY.md` and the relevant `INTEGRATION.md` notes |
| Knowledge pack facts about Pyro | the files in `backend/knowledge/` (and reconcile against the CV — CV wins) |

If a change spans several of these, update all of them. When unsure whether a doc
needs updating, check it rather than skip it.

## Two repos — keep them in sync
This project lives in the `learning-ai-engineering` monorepo **and** as the standalone
public repo **`pyro-chat-bot`**. After committing project changes to the monorepo, mirror
them:
```bash
git subtree push --prefix=projects/learning-langchain pyro-chat-bot main
```
Both repos are **public**.

## Never commit secrets
`.env`, `*-CV.pdf`, and `backend/data/` are gitignored and must stay out of git. The CV
contains a phone number; the knowledge pack must not include it. Don't run
`rm -rf backend/data` — it's live runtime data (Chroma + SQLite).

## Style
Match the existing voice in the docs (concise, table-driven, honest about what's not yet
built). Don't overclaim capabilities; flag anything unverified.
