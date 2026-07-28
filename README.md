# ClauseClear

**Understand any contract before you sign it.** Paste a lease, freelance
contract, job offer, NDA or terms of service and get a plain-English breakdown
of the risky clauses, what's missing, and exactly what to push back on.

👉 **Live:** https://clauseclear-app.azurewebsites.net

Most people sign contracts they don't fully understand — leases, gig-work
agreements, NDAs, job offers — because a lawyer costs hundreds and the language
is deliberately dense. ClauseClear reads the document and gives you:

- 🎯 a **risk score** and plain-English summary
- ⚠️ the **clauses that matter**, each with *what it means*, *why it matters*,
  and *what to ask for instead*
- 🕳️ **protections that seem to be missing**
- 💬 **questions to ask** before you sign

## Honest about what it is

- **AI-powered, not a lawyer.** It's a fast first read to help you spot problems
  and ask better questions — **not legal advice**. For anything important, get a
  professional to review it.
- **Nothing is stored.** Your text is sent to the AI to analyse and is not saved
  by ClauseClear.
- **Free**, no signup.

## How it works

A tiny WSGI backend forwards your text to a free, OpenAI-compatible LLM gateway
and asks for a structured review, then returns clean JSON the frontend renders.
No API key required, no database, pure Python standard library. The frontend is
a single static page.

```
Browser ──POST /api/review──▶ ClauseClear (WSGI) ──▶ free LLM gateway
        ◀──── structured review JSON ─────────────◀
```

## Run locally

```bash
python3 app.py        # serves http://localhost:8000
```

No dependencies for local dev beyond the standard library (production uses
`gunicorn`).

## Configuration (optional)

| Env var | Default | Purpose |
| --- | --- | --- |
| `CLAUSECLEAR_MODEL` | `kilo-auto/free` | model id on the gateway |
| `CLAUSECLEAR_GATEWAY` | Kilo gateway URL | OpenAI-compatible endpoint |

Bring your own key by pointing `CLAUSECLEAR_GATEWAY` at any OpenAI-compatible
provider.

## License

MIT.
