"""Render reports for people (terminal) and for programs (JSON)."""
from __future__ import annotations

import json
import os
import sys

from .models import Report

_MARK = {"verified": "✓", "unverified": "?", "contradicted": "✗"}
_COLOR = {"verified": "32", "unverified": "33", "contradicted": "31", "dim": "2", "bold": "1"}


def _use_color(stream) -> bool:
    return hasattr(stream, "isatty") and stream.isatty() and not os.environ.get("NO_COLOR")


def _paint(text: str, color: str, on: bool) -> str:
    return f"\033[{_COLOR[color]}m{text}\033[0m" if on else text


def _short(text: str, n: int = 110) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def to_text(report: Report, stream=None, verbose: bool = False) -> str:
    on = _use_color(stream or sys.stdout)
    t = report.turn
    lines = [_paint(f"Turn {t.index}: {_short(t.prompt, 80)}", "bold", on),
             _paint(f"  {len(t.actions)} tool calls, {len(report.findings)} claims checked", "dim", on)]
    for f in report.findings:
        if f.verdict == "verified" and not verbose:
            continue
        lines.append(f"  {_paint(_MARK[f.verdict] + ' ' + f.verdict.upper(), f.verdict, on)}  {_short(f.claim.text)}")
        lines.append(_paint(f"      why: {f.reason}", "dim", on))
        for a in f.evidence[:2]:
            lines.append(_paint(f"      call #{a.index}: {_short(a.label(), 90)}", "dim", on))
    if report.unreported_failures:
        lines.append(_paint("  ✗ FAILED CALLS NOT MENTIONED IN THE SUMMARY", "contradicted", on))
        for a in report.unreported_failures[:5]:
            lines.append(f"      call #{a.index}: {_short(a.label(), 80)}  ({a.reason})")
    verified = sum(f.verdict == "verified" for f in report.findings)
    lines.append(_paint(f"  {verified} verified · {len(report.unverified)} unverified · "
                        f"{len(report.contradicted)} contradicted · {len(report.unreported_failures)} unreported failures",
                        "dim", on))
    return "\n".join(lines)


def to_dict(report: Report) -> dict:
    return {
        "turn": report.turn.index,
        "prompt": report.turn.prompt,
        "tool_calls": len(report.turn.actions),
        "findings": [
            {"claim": f.claim.text, "kind": f.claim.kind, "targets": f.claim.targets, "verdict": f.verdict,
             "reason": f.reason, "evidence": [{"call": a.index, "tool": a.tool, "status": a.status} for a in f.evidence]}
            for f in report.findings
        ],
        "unreported_failures": [{"call": a.index, "tool": a.tool, "label": a.label(), "reason": a.reason}
                                for a in report.unreported_failures],
    }


def to_json(reports: list[Report]) -> str:
    return json.dumps([to_dict(r) for r in reports], indent=2, ensure_ascii=False)
