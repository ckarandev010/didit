"""Match each claim to the tool calls that could back it up, and give a verdict."""
from __future__ import annotations

import os
import re

from .actions import tests_passed
from .claims import extract
from .models import Action, Claim, Finding, Report, Turn

# Which kinds of tool call can support which kind of claim.
SUPPORT = {
    "test": {"test"},
    "git_push": {"git_push"},
    "git_commit": {"git_commit"},
    "send": {"send", "command", "other"},
    "draft": {"draft", "other", "file_write"},
    "install": {"install"},
    "delete": {"delete", "command"},
    "build": {"build", "command"},
    "file_write": {"file_write", "command", "other", "draft"},
    "command": {"command", "build", "install", "test", "other", "git_push", "git_commit", "delete"},
}

_TEST_RESULT_WORDS = re.compile(r"\bpass(es|ed|ing)?\b|\bgreen\b", re.I)
_WORD = re.compile(r"[A-Za-z0-9_]{3,}")


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def _mentions(action: Action, target: str) -> bool:
    haystack = _norm(action.text())
    t = _norm(target).strip("`'\" ")
    if t in haystack:
        return True
    base = t.rsplit("/", 1)[-1]
    return len(base) >= 4 and base in haystack


def _similar(a: Action, b: Action) -> bool:
    if a.tool != b.tool:
        return False
    wa, wb = set(_WORD.findall(a.label().lower())), set(_WORD.findall(b.label().lower()))
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.5


def _recovered(failed: Action, actions: list[Action]) -> bool:
    """A failure counts as recovered if a similar later call worked, or a later call worked on the same file."""
    later_ok = [a for a in actions[failed.index + 1:] if a.status == "ok"]
    if any(_similar(failed, later) for later in later_ok):
        return True
    path = failed.input.get("file_path") or failed.input.get("path")
    return bool(path) and any(a.kind != "file_read" and _mentions(a, str(path)) for a in later_ok)


def _verdict(claim: Claim, turn: Turn, check_files: bool) -> Finding:
    allowed = SUPPORT.get(claim.kind, {"command", "file_write", "other"})
    if claim.kind == "test" and not _TEST_RESULT_WORDS.search(claim.text):
        allowed = allowed | {"command", "other"}      # "I tested X" can be any hands-on check
    candidates = [a for a in turn.actions if a.kind in allowed]

    if claim.targets:
        touched = [a for a in candidates if any(_mentions(a, t) for t in claim.targets)]
        if not touched:
            # The target might have been written by a shell command or another tool kind.
            touched = [a for a in turn.actions if a.kind != "file_read" and any(_mentions(a, t) for t in claim.targets)]
        if not touched and candidates:
            return Finding(claim, "unverified",
                           f"no tool call touched {', '.join(claim.targets[:3])}")
        candidates = touched or candidates

    if not candidates:
        return Finding(claim, "unverified", f"no {claim.kind.replace('_', ' ')} tool call in this turn")

    last = candidates[-1]
    if claim.kind == "test" and last.kind == "test":
        if last.status == "failed":
            return Finding(claim, "contradicted", f"the last test run failed ({last.reason})", [last])
        if tests_passed(last):
            return Finding(claim, "verified", "the last test run passed", [last])
        return Finding(claim, "unverified", "a test command ran but its output does not show a pass", [last])

    if last.status == "failed" and not _recovered(last, turn.actions):
        return Finding(claim, "contradicted", f"the matching call failed: {last.reason}", [last])
    if last.status == "pending":
        return Finding(claim, "unverified", "the matching call has no recorded result", [last])
    if last.status == "silent":
        return Finding(claim, "unverified", f"the matching call {last.reason}", [last])

    if check_files and claim.kind == "file_write":
        for action in candidates:
            path = action.input.get("file_path")
            if path:
                full = path if os.path.isabs(path) else os.path.join(turn.cwd or ".", path)
                if not os.path.exists(full):
                    return Finding(claim, "contradicted", f"{path} does not exist on disk now", [action])

    ok = [a for a in candidates if a.status == "ok"]
    return Finding(claim, "verified", "a matching call succeeded", ok[-2:] or [last])


_ADMITS_FAILURE = re.compile(r"\b(fail(ed|s|ure)?|error|could(n't| not)|unable|did(n't| not)|broke|blocked|not yet)\b", re.I)


def check_turn(turn: Turn, check_files: bool = False, extractor=extract) -> Report:
    """Check one turn. `extractor` turns the summary into claims (rules by default; see didit.llm)."""
    findings = [_verdict(c, turn, check_files) for c in extractor(turn.summary)]
    unreported = []
    if not _ADMITS_FAILURE.search(turn.summary):
        unreported = [a for a in turn.actions
                      if a.status == "failed" and a.kind != "file_read" and not _recovered(a, turn.actions)]
    return Report(turn=turn, findings=findings, unreported_failures=unreported)
