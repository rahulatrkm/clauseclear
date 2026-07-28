"""ClauseClear — backend proxy + static server (WSGI, pure standard library).

A small, honest backend that lets a browser call a free LLM to review a
contract. It:

  * serves the static frontend (``web/index.html``)
  * exposes ``POST /api/review`` which forwards a contract to the Kilo AI
    Gateway (keyless free-tier inference), asks for a structured review, and
    returns clean JSON with permissive CORS

Why a proxy at all: the gateway does not send CORS headers, so a purely static
page cannot call it from the browser. This tiny forwarder is the minimum backend
that makes the product real, and it runs on a free tier.

No secrets required. No data stored. Pure stdlib.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

_WEB_DIR = Path(__file__).resolve().parent / "web"

GATEWAY_URL = os.environ.get(
    "CLAUSECLEAR_GATEWAY", "https://api.kilo.ai/api/gateway/v1/chat/completions"
)
MODEL = os.environ.get("CLAUSECLEAR_MODEL", "kilo-auto/free")
MAX_CHARS = 16000  # keep prompts within free-model context; longer text is trimmed

SYSTEM_PROMPT = (
    "You are ClauseClear, a contract-review assistant for non-lawyers. You read a "
    "contract (or an excerpt) and explain, in plain English, what a normal person "
    "should worry about before signing. You are practical, specific and honest. "
    "You are NOT a lawyer and this is NOT legal advice.\n\n"
    "Return STRICT JSON ONLY — no markdown, no prose outside the JSON — with this "
    "exact shape:\n"
    "{\n"
    '  "summary": string,                // 2-3 sentences, plain English\n'
    '  "risk_score": number,             // 0 (safe) to 100 (dangerous)\n'
    '  "risk_label": string,             // e.g. "Low", "Moderate", "High", "Very high"\n'
    '  "clauses": [                      // the notable clauses, worst first\n'
    "    {\n"
    '      "title": string,\n'
    '      "severity": "high" | "medium" | "low",\n'
    '      "what_it_means": string,      // decode the legalese\n'
    '      "why_it_matters": string,     // the real-world consequence\n'
    '      "suggested_pushback": string  // exactly what to ask to change\n'
    "    }\n"
    "  ],\n"
    '  "missing_protections": [string],  // things that SHOULD be there but are not\n'
    '  "questions_to_ask": [string]      // concrete questions for the other party\n'
    "}\n\n"
    "Rules: be concrete (quote or paraphrase the actual terms). If the text is not "
    "a contract, set risk_score 0 and say so in summary. Never invent clauses that "
    "are not present."
)


def _cors(headers: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return headers + [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "POST, GET, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
    ]


def _json_response(start, status, payload, extra=None):
    body = json.dumps(payload).encode("utf-8")
    headers = _cors([("Content-Type", "application/json; charset=utf-8"),
                     ("Content-Length", str(len(body)))] + (extra or []))
    start(status, headers)
    return [body]


def _extract_json(text: str) -> dict | None:
    """Pull the first balanced JSON object out of a model reply."""
    if not text:
        return None
    # fast path
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # find first '{' and match braces
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


def _call_gateway(contract: str, doc_type: str) -> dict:
    user = (
        f"Contract type the user believes this is: {doc_type or 'unspecified'}.\n\n"
        f"Review the following contract text:\n\n{contract[:MAX_CHARS]}"
    )
    req_body = json.dumps({
        "model": MODEL,
        "temperature": 0.2,
        "max_tokens": 1600,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        GATEWAY_URL, data=req_body, method="POST",
        headers={"Content-Type": "application/json",
                 "User-Agent": "clauseclear/1.0"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode("utf-8"))
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    parsed = _extract_json(content)
    if parsed is None:
        raise ValueError("The model returned an unparseable response. Try again.")
    return parsed


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    if method == "OPTIONS":
        start_response("204 No Content", _cors([("Content-Length", "0")]))
        return [b""]

    if path in ("/api/review",) and method == "POST":
        try:
            size = int(environ.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            size = 0
        if size <= 0 or size > 200_000:
            return _json_response(start_response, "400 Bad Request",
                                  {"error": "Please paste some contract text (up to ~50 pages)."})
        raw = environ["wsgi.input"].read(size)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _json_response(start_response, "400 Bad Request",
                                  {"error": "Invalid request."})
        contract = (payload.get("text") or "").strip()
        doc_type = (payload.get("type") or "").strip()
        if len(contract) < 40:
            return _json_response(start_response, "400 Bad Request",
                                  {"error": "That's too short to review — paste the full clause or document."})
        try:
            result = _call_gateway(contract, doc_type)
        except urllib.error.HTTPError as exc:
            code = exc.code
            if code == 429:
                return _json_response(start_response, "429 Too Many Requests",
                                      {"error": "The free AI is busy right now (rate limit). Please try again in a minute."})
            return _json_response(start_response, "502 Bad Gateway",
                                  {"error": f"AI service error ({code}). Please try again."})
        except (urllib.error.URLError, TimeoutError):
            return _json_response(start_response, "504 Gateway Timeout",
                                  {"error": "The AI took too long. Try a shorter excerpt."})
        except ValueError as exc:
            return _json_response(start_response, "502 Bad Gateway", {"error": str(exc)})
        result.setdefault("_disclaimer",
                          "ClauseClear is an AI assistant, not a lawyer. This is not legal advice.")
        return _json_response(start_response, "200 OK", result)

    if path == "/healthz":
        return _json_response(start_response, "200 OK", {"status": "ok"})

    # static files
    if method == "GET":
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        if "/" not in rel and ".." not in rel:
            fp = _WEB_DIR / rel
            if fp.exists() and fp.is_file():
                ctype = ("text/html; charset=utf-8" if rel.endswith(".html")
                         else "text/plain; charset=utf-8")
                body = fp.read_bytes()
                start_response("200 OK", _cors([("Content-Type", ctype),
                                                ("Content-Length", str(len(body)))]))
                return [body]

    return _json_response(start_response, "404 Not Found", {"error": "not found"})


app = application


def serve(port: int = 8000):  # pragma: no cover
    from wsgiref.simple_server import make_server
    print(f"ClauseClear on http://localhost:{port}")
    make_server("", port, application).serve_forever()


if __name__ == "__main__":  # pragma: no cover
    serve(int(os.environ.get("PORT", "8000")))
