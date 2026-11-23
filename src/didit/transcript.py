"""Load agent sessions into Turns.

Two formats are supported:

* Claude Code session logs (``~/.claude/projects/<project>/<session>.jsonl``).
* A small neutral JSON format, so any agent framework can be checked:

  {"prompt": "...", "summary": "...",
   "actions": [{"tool": "Bash", "input": {"command": "pytest"}, "output": "3 passed", "error": false}]}
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .actions import classify
from .models import Action, Turn

_NOISE_PREFIXES = ("<system-reminder>", "<ide_", "<command-", "<local-command", "<task-notification", "Caveat:")


def _block_text(content) -> str:
    """Flatten a message's content (string or list of blocks) to text."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "tool_result":
                parts.append(_block_text(block.get("content")))
    return "\n".join(p for p in parts if p)


def _human_text(record: dict) -> str | None:
    """Return the prompt if this record is a message typed by the human, else None."""
    if record.get("isMeta") or record.get("isSidechain"):
        return None
    content = (record.get("message") or {}).get("content")
    if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return None
    text = _block_text(content).strip()
    if not text:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith(_NOISE_PREFIXES)]
    return "\n".join(lines).strip() or None


def load_claude_code(path: str | os.PathLike) -> list[Turn]:
    turns: list[Turn] = []
    by_id: dict[str, Action] = {}
    current: Turn | None = None
    texts: list[tuple[int, str]] = []      # (number of actions before this text, text)

    def close():
        if current is None:
            return
        n = len(current.actions)
        after = [t for pos, t in texts if pos == n]
        current.summary = "\n".join(after) if after else (texts[-1][1] if texts else "")
        for action in current.actions:
            classify(action)
        turns.append(current)

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = record.get("type")
            if kind == "user":
                prompt = _human_text(record)
                if prompt is not None:
                    close()
                    current = Turn(index=len(turns), prompt=prompt, cwd=record.get("cwd", ""))
                    texts = []
                    continue
                for block in (record.get("message") or {}).get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        action = by_id.get(block.get("tool_use_id", ""))
                        if action is not None:
                            action.output = _block_text(block.get("content"))
                            action.is_error = bool(block.get("is_error"))
                            action.status = "ok"
            elif kind == "assistant" and current is not None and not record.get("isSidechain"):
                for block in (record.get("message") or {}).get("content") or []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text" and block.get("text", "").strip():
                        texts.append((len(current.actions), block["text"].strip()))
                    elif block.get("type") == "tool_use":
                        action = Action(index=len(current.actions), tool=block.get("name", "?"),
                                        input=block.get("input") or {}, status="pending")
                        current.actions.append(action)
                        by_id[block.get("id", "")] = action
    close()
    return turns


def load_simple(path: str | os.PathLike) -> list[Turn]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else [data]
    turns = []
    for i, item in enumerate(items):
        turn = Turn(index=i, prompt=item.get("prompt", ""), summary=item.get("summary", ""), cwd=item.get("cwd", ""))
        for j, a in enumerate(item.get("actions", [])):
            action = Action(index=j, tool=a.get("tool", "?"), input=a.get("input") or {},
                            output=a.get("output", ""), is_error=bool(a.get("error")))
            classify(action)
            turn.actions.append(action)
        turns.append(turn)
    return turns


def load(path: str | os.PathLike) -> list[Turn]:
    """Load a session file, or the newest .jsonl session in a directory."""
    p = Path(path)
    if p.is_dir():
        sessions = sorted(p.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
        if not sessions:
            raise FileNotFoundError(f"no .jsonl sessions in {p}")
        p = sessions[-1]
    if p.suffix == ".json":
        return load_simple(p)
    return load_claude_code(p)
