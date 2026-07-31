"""Publish the ClauseClear launch article to dev.to via the official API.

    DEVTO_API_KEY=<key> python publish_devto.py --publish
"""
from __future__ import annotations
import json, os, sys, urllib.request, urllib.error

LIVE = "https://clauseclear-app.azurewebsites.net"
REPO = "https://github.com/rahulatrkm/clauseclear"

BODY = f"""\
## The contract clause that almost cost my friend their side projects

A friend nearly signed a freelance contract that assigned the company **all** the
IP they created — including personal side projects done on their own time — plus
a 3-year industry-wide non-compete and net-90 payment terms. To them it just
looked like normal legal boilerplate. It wasn't.

Most of us sign leases, freelance agreements, NDAs and job offers we don't fully
understand, because a lawyer costs hundreds and the language is deliberately
dense. So I built a small tool to make contracts legible for non-lawyers.

## What it does

Paste a contract (or the clauses you're unsure about) into
[ClauseClear]({LIVE}) and it returns:

- a **plain-English summary** and a **risk score**
- the **clauses that actually matter** — each with *what it means*, *why it
  matters*, and *what to ask for instead*
- **protections that seem to be missing**
- **questions to ask** before you sign

It's honest that it's an AI first-read, **not legal advice** — but as a "should I
worry about this?" gut-check before you sign, it's genuinely useful.

## How it's built

- A tiny Python (WSGI, standard-library) backend forwards your text to a free,
  OpenAI-compatible LLM and asks for a **structured** review
- The frontend is a single static page — risk gauge, severity-colored clause
  cards, copy-to-clipboard report
- **Nothing is stored.** No signup. Free to use.
- Open source (MIT): [{REPO}]({REPO})

Getting the model to reliably return clean JSON (instead of chatty preamble or
truncated output) was the fiddly part — solved with a strict "output only JSON"
contract, reasoning-strip, truncated-JSON repair, and retries.

## Try it

Paste something gnarly — an old lease, a gig contract, a ToS — and see what it
flags: **{LIVE}**

I'd love feedback on the review quality: what did it miss, and is the "suggested
pushback" actually useful or too generic?
"""

ARTICLE = {"article": {
    "title": "I built a tool that reads your contract and flags the risky clauses in plain English",
    "published": False,
    "tags": ["python", "ai", "webdev", "showdev"],
    "canonical_url": REPO,
    "description": ("Paste a lease, freelance contract, NDA or job offer and get a plain-English "
                    "breakdown of the risky clauses, what's missing, and what to push back on. Free."),
    "body_markdown": BODY,
}}

def find_existing(key, title):
    for state in ("unpublished", "published"):
        req = urllib.request.Request(f"https://dev.to/api/articles/me/{state}?per_page=50",
            headers={"api-key": key, "User-Agent": "clauseclear-pub/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            for a in json.loads(r.read().decode()):
                if a.get("title") == title:
                    return a
    return None

def main():
    key = os.environ.get("DEVTO_API_KEY")
    if not key:
        print("Set DEVTO_API_KEY", file=sys.stderr); return 1
    ARTICLE["article"]["published"] = "--publish" in sys.argv
    existing = find_existing(key, ARTICLE["article"]["title"])
    data = json.dumps(ARTICLE).encode()
    if existing:
        req = urllib.request.Request(f"https://dev.to/api/articles/{existing['id']}", data=data,
            method="PUT", headers={"Content-Type": "application/json", "api-key": key,
                                   "User-Agent": "clauseclear-pub/1.0"})
    else:
        req = urllib.request.Request("https://dev.to/api/articles", data=data, method="POST",
            headers={"Content-Type": "application/json", "api-key": key, "User-Agent": "clauseclear-pub/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode())
        print(("PUBLISHED" if "--publish" in sys.argv else "DRAFT") + ":", res.get("url"))
    except urllib.error.HTTPError as e:
        print(f"error {e.code}: {e.read().decode()[:300]}", file=sys.stderr); return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
