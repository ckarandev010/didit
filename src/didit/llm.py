"""Optional claim extraction with a local model (Ollama), for claims the rules miss.

The model only FINDS claims. Verdicts still come from the deterministic checker, and every claim the model
returns must quote a sentence that really appears in the agent's message: anything it invents is dropped.

Settings (environment):
  DIDIT_OLLAMA_HOST   default http://localhost:11434
  DIDIT_MODEL         default qwen2.5:7b-instruct
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .claims import _NOT_A_CLAIM, _SPEECH, _ZERO_FAILURES, _sentences, _targets, extract as extract_rules
from .models import Claim

KINDS = ["test", "git_push", "git_commit", "send", "draft", "install", "delete", "build", "file_write", "command"]

PROMPT = """You read the final message an AI coding agent wrote after finishing a task.
List every sentence in which the agent says that some work IS DONE: something was changed, created, run,
installed, deleted, committed, pushed, sent, or that tests pass. Include passive or indirect wording such as
"The changes are now on GitHub" or "`app.py` now handles empty input".

Do NOT include: plans or offers ("I'll", "want me to"), questions, instructions to the user, explanations of how
code works, quoted text, or admitted failures ("couldn't", "failed").

For each claim give:
- "sentence": the sentence copied EXACTLY from the message
- "kind": one of {kinds}
  (test = tests ran/pass; file_write = a file or document was created or changed; command = something was run,
   started or deployed; the others are what they say)

Message:
<<<
{message}
>>>"""

SCHEMA = {
    "type": "object",
    "properties": {"claims": {"type": "array", "items": {
        "type": "object",
        "properties": {"sentence": {"type": "string"}, "kind": {"type": "string", "enum": KINDS}},
        "required": ["sentence", "kind"]}}},
    "required": ["claims"],
}


# A model-found claim must still read like finished work, and must pass the same filters as rule claims.
_DONE_SIGNAL = re.compile(r"\b(?:\w{3,}ed|done|complete|live|ready|now|passing|green|pass(?:es)?|written|built|"
                          r"sent|run|set up|in place|merged|up to date)\b", re.I)


def _acceptable(sentence: str) -> bool:
    spoken = _SPEECH.sub('""', sentence)
    return bool(_DONE_SIGNAL.search(spoken)) and not _NOT_A_CLAIM.search(_ZERO_FAILURES.sub(" ", spoken))


class LLMUnavailable(RuntimeError):
    pass


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    path = Path(base) / "didit"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ask(message: str, model: str, host: str, timeout: float) -> list[dict]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT.format(kinds=", ".join(KINDS), message=message)}],
        "format": SCHEMA,
        "stream": False,
        "options": {"temperature": 0, "seed": 0},
    }
    request = urllib.request.Request(host.rstrip("/") + "/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            reply = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LLMUnavailable(f"could not reach Ollama at {host}: {exc}") from exc
    try:
        return json.loads(reply["message"]["content"]).get("claims", [])
    except (KeyError, json.JSONDecodeError, AttributeError):
        return []


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).strip().lower()


def extract_llm(summary: str, model: str | None = None, host: str | None = None,
                timeout: float = 120, use_cache: bool = True) -> list[Claim]:
    """Claims found by the model, keeping only sentences that really occur in the summary."""
    model = model or os.environ.get("DIDIT_MODEL", "qwen2.5:7b-instruct")
    host = host or os.environ.get("DIDIT_OLLAMA_HOST", "http://localhost:11434")
    if not summary.strip():
        return []

    key = hashlib.sha256(f"{model}\n{PROMPT}\n{summary}".encode()).hexdigest()[:32]
    cache = _cache_dir() / f"{key}.json"
    if use_cache and cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
    else:
        raw = _ask(summary, model, host, timeout)
        if use_cache:
            cache.write_text(json.dumps(raw), encoding="utf-8")

    sentences = {_norm(s): s for s in _sentences(summary)}
    claims, seen = [], set()
    for item in raw:
        if not isinstance(item, dict) or item.get("kind") not in KINDS:
            continue
        quoted = _norm(str(item.get("sentence", "")))
        if len(quoted) < 10:
            continue
        # Grounding: the quote must be (part of) a real sentence in the message.
        match = sentences.get(quoted) or next((s for n, s in sentences.items() if quoted in n or (n in quoted and len(n) > 12)), None)
        if match is None or (match, item["kind"]) in seen or not _acceptable(match):
            continue
        seen.add((match, item["kind"]))
        claims.append(Claim(text=match, kind=item["kind"], targets=_targets(match)))
    return claims


def extract_hybrid(summary: str, **kwargs) -> list[Claim]:
    """Rule claims first (precise), plus whatever the model found that the rules missed."""
    claims = extract_rules(summary)
    have = {(_norm(c.text), c.kind) for c in claims}
    have_sentences = {_norm(c.text) for c in claims}
    for c in extract_llm(summary, **kwargs):
        if _norm(c.text) in have_sentences or (_norm(c.text), c.kind) in have:
            continue        # the rules already handled this sentence; trust them over the model
        claims.append(c)
    return claims
