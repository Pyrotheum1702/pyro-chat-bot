# Knowledge pack ("About Me")

These markdown files are the chatbot's knowledge base about **Pyro**. They are
seeded into the vector store on startup (chunked → embedded → Chroma) so the
public "chat with me" bot can answer questions about Pyro grounded in this
content.

Edit these freely — re-seeding picks up changes. Keep facts accurate; the bot
will state them to visitors. Drafted from pyrotheum1702.com — **review and
correct.**

Files:
- `about.md` — bio, current role, who Pyro is
- `experience.md` — work history
- `projects.md` — selected work
- `skills.md` — technical expertise
- `honors.md` — honors & awards
- `faq.md` — anticipated visitor questions

Note: the source CV (`source/`, gitignored) contains a phone number that is
**intentionally excluded** from this knowledge base — don't add it.
