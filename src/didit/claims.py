"""Pull checkable claims out of an agent's final message, using plain rules (no model).

A claim is a sentence where the agent says it has done something: "I saved config.py", "All tests pass",
"Committed and pushed". Explanations, plans, questions, offers and admitted failures are not claims.
"""
from __future__ import annotations

import re

from .models import Claim

# Verb patterns per kind. Order matters: the first kind whose verb matches wins.
_VERBS = [
    ("git_push", r"pushed"),
    ("git_commit", r"committed|created (?:a |the )?commit"),
    ("send", r"sent|emailed|posted|published"),
    ("draft", r"drafted"),
    ("install", r"installed"),
    ("delete", r"deleted|removed"),
    ("build", r"built|compiled"),
    ("test", r"tested|ran (?:the |all )?(?:\w+ )?(?:tests?|test suite|suite|specs)"),
    ("file_write", r"saved|wrote|created|added|updated|edited|fixed|renamed|changed|modified|replaced|refactored|"
                   r"implemented|generated|rendered|moved|marked|logged|recorded|stored"),
    ("command", r"ran|executed|launched|started|restarted|migrated|deployed|configured|verified|confirmed|checked"),
]

# "I fixed", "I've also updated", "we just pushed": the agent is the one acting ...
_ACTOR = r"\b(?:I|we)(?:['’](?:ve|m))?(?: have| had)?(?: \w+){0,2}? "
_ACTOR_CLAIM = {kind: re.compile(_ACTOR + rf"(?:{verbs})\b", re.I) for kind, verbs in _VERBS}
# ... or a summary line that starts with the verb: "Saved config.py", "Fixed the off-by-one".
_LEADING_VERB = {kind: re.compile(rf"^(?:also |then |and )?(?:{verbs})\b", re.I) for kind, verbs in _VERBS}
# Test results are claims whoever the subject is: "All 12 tests pass", "tests are green".
_TEST_RESULT = re.compile(r"\btests?\b[^.]{0,40}\b(?:pass(?:es|ed|ing)?|green|succeed(?:ed|s)?)\b|"
                          r"\b\d+ (?:tests? )?passed\b", re.I)

# Plans, offers, conditions, questions and admitted problems are not claims of finished work.
_NOT_A_CLAIM = re.compile(
    r"\?|\b(?:will|I'll|we'll|I'd|we'd|going to|could|should|would|might|want me|let me|next step|"
    r"if you|once you|when you|before you|you can|you'll|need to|plan to|to do)\b|"
    r"\b(?:not|never|failed|unable|couldn't|skipped|didn't|wasn't|isn't|haven't|hasn't|doesn't|don't)\b|n't\b",
    re.I,
)

_ZERO_FAILURES = re.compile(r"\b(?:0|zero|no) (?:failed|failures?|errors?)\b", re.I)

_BACKTICK = re.compile(r"`([^`]{2,120})`")
_LINK_TEXT = re.compile(r"\[([^\]]{2,120})\]\([^)]*\)")
_LINK_URL = re.compile(r"\]\(([^)\s]{4,300})\)")
_SPEECH = re.compile(r"[\"“][^\"”]{12,}[\"”]")   # quoted speech, not a claim by the agent
_PATHLIKE = re.compile(r"(?<![\w/\\])((?:[\w.-]+[/\\])*[\w-]+\.[A-Za-z]\w{0,5})(?![\w/\\])")
_QUOTED = re.compile(r"\"([^\"]{3,60})\"")


def _sentences(summary: str) -> list[str]:
    out = []
    for raw in summary.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "|", "```", ">")):
            continue
        line = re.sub(r"^([-*+]|\d+[.)])\s+", "", line)        # list bullets
        line = line.replace("**", "").replace("__", "")
        for part in re.split(r"(?<=[.!;])\s+(?=[A-Z`\[])", line):
            part = part.strip()
            if len(part) >= 6:
                out.append(part)
    return out


def _targets(sentence: str) -> list[str]:
    found: list[str] = []
    for pattern in (_BACKTICK, _LINK_URL, _LINK_TEXT, _QUOTED):
        found += [m.group(1).strip() for m in pattern.finditer(sentence)]
    plain = _BACKTICK.sub(" ", _LINK_TEXT.sub(" ", sentence))
    found += [m.group(1) for m in _PATHLIKE.finditer(plain) if not re.fullmatch(r"\d+(\.\d+)*", m.group(1))]
    seen, unique = set(), []
    for t in found:
        key = t.lower()
        if key not in seen and not re.fullmatch(r"(e\.g|i\.e|etc)\.?", key):
            seen.add(key)
            unique.append(t)
    return unique


def _kind(sentence: str) -> str | None:
    sentence = _SPEECH.sub('""', sentence)
    for kind, _ in _VERBS:
        if _ACTOR_CLAIM[kind].search(sentence) or _LEADING_VERB[kind].search(sentence):
            return kind
    return "test" if _TEST_RESULT.search(sentence) else None


_BARE = {kind: re.compile(rf"\b(?:{verbs})\b", re.I) for kind, verbs in _VERBS}
# Actions with side effects that deserve their own check when they ride along in a compound sentence:
# "I committed the fix and pushed it" is two claims.
_RIDERS = ("git_push", "git_commit", "send", "install", "delete", "test")


def extract(summary: str) -> list[Claim]:
    claims = []
    for sentence in _sentences(summary):
        spoken = _SPEECH.sub('""', sentence)
        # "0 failed" / "no failures" report success, they are not admissions of failure.
        if _NOT_A_CLAIM.search(_ZERO_FAILURES.sub(" ", spoken)):
            continue
        kind = _kind(sentence)
        if not kind:
            continue
        kinds = [kind] + [k for k in _RIDERS if k != kind and
                          (_BARE[k].search(spoken) or (k == "test" and _TEST_RESULT.search(spoken)))]
        targets = _targets(sentence)
        claims.extend(Claim(text=sentence, kind=k, targets=targets) for k in kinds)
    return claims
