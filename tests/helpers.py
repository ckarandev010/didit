"""Build small synthetic Claude Code session logs for tests (no real sessions are ever committed)."""
from __future__ import annotations

import json
import itertools

_ids = itertools.count(1)


def user(text: str) -> dict:
    return {"type": "user", "cwd": "/tmp/project", "message": {"role": "user", "content": text}}


def call(tool: str, inp: dict, output: str = "", error: bool = False) -> list[dict]:
    tid = f"toolu_{next(_ids)}"
    return [
        {"type": "assistant", "message": {"role": "assistant",
                                          "content": [{"type": "tool_use", "id": tid, "name": tool, "input": inp}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tid, "content": output, "is_error": error}]}},
    ]


def say(text: str) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def session(tmp_path, *records) -> str:
    flat = []
    for r in records:
        flat.extend(r if isinstance(r, list) else [r])
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in flat), encoding="utf-8")
    return str(path)
