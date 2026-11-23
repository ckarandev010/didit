"""Decide what each tool call was and whether it worked, using plain rules (no model)."""
from __future__ import annotations

import re

from .models import Action

WRITE_TOOLS = {"write", "edit", "multiedit", "notebookedit", "str_replace_editor", "create_file", "apply_patch"}
READ_TOOLS = {"read", "glob", "grep", "ls", "view"}
SHELL_TOOLS = {"bash", "powershell", "shell", "terminal", "run_command", "exec"}

_COMMAND_KINDS = [
    ("test", re.compile(r"\b(pytest|py\.test|unittest|npm (run )?test|yarn test|pnpm test|go test|cargo test|"
                        r"mvn test|gradle test|jest|vitest|rspec|phpunit|ctest|tox)\b")),
    ("git_commit", re.compile(r"\bgit\b[^|;&]*\bcommit\b")),
    ("git_push", re.compile(r"\bgit\b[^|;&]*\bpush\b")),
    ("install", re.compile(r"\b(pip3? install|npm (i|install)|yarn add|pnpm add|apt(-get)? install|brew install|"
                           r"cargo add|go get|winget install|choco install)\b")),
    ("delete", re.compile(r"(^|[\s;&|])(rm|rmdir|del|Remove-Item|git rm)\s")),
    ("build", re.compile(r"\b(make|cmake --build|npm run build|cargo build|go build|tsc|docker build|idf\.py build)\b")),
]

# Shell commands that only look at things. Reading a file is not evidence that it was changed.
_READ_ONLY = re.compile(r"^\s*(?:cd [^;&|]+(?:&&|;)\s*)?(?:cat|head|tail|less|more|grep|rg|ls|dir|find|wc|stat|file|"
                        r"diff|type|Get-Content|Get-ChildItem|Select-String|git (?:status|diff|log|show|branch))\b")
_WRITES = re.compile(r">|\btee\b|\bsed -i\b|-exec\b|\|\s*(?:sh|bash|python)\b")

_FAIL_PATTERNS = [
    (re.compile(r"Exit code [1-9]\d*"), "non-zero exit code"),
    (re.compile(r"^Traceback \(most recent call last\)", re.M), "Python traceback"),
    (re.compile(r"command not found|is not recognized as (an internal|the name)", re.I), "command not found"),
    (re.compile(r"\bNo such file or directory\b|\bcannot find (the )?(path|file)\b", re.I), "missing file"),
    (re.compile(r"^(fatal|error): ", re.M | re.I), "tool reported an error"),
    (re.compile(r"\bPermission denied\b|\bAccess is denied\b", re.I), "permission denied"),
    (re.compile(r"! \[rejected\]|failed to push", re.I), "push rejected"),
    (re.compile(r"String to replace not found|old_string .* not found|File has not been read yet", re.I), "edit not applied"),
]

_TEST_FAILED = re.compile(r"\b(\d+) (failed|errors?)\b|^FAILED\b|\bTests? failed\b|\bFAIL\b", re.I | re.M)
_TEST_PASSED = re.compile(r"\b(\d+) passed\b|\bOK\b|\bAll tests passed\b|\bTests?:\s+\d+ passed", re.I)


def classify(action: Action) -> Action:
    """Fill in action.kind and action.status."""
    tool = action.tool.lower().split("__")[-1]
    command = str(action.input.get("command", ""))

    if tool in WRITE_TOOLS:
        action.kind = "file_write"
    elif tool in READ_TOOLS:
        action.kind = "file_read"
    elif tool in SHELL_TOOLS or command:
        action.kind = "command"
        for kind, pattern in _COMMAND_KINDS:
            if pattern.search(command):
                action.kind = kind
                break
        else:
            if _READ_ONLY.match(command) and not _WRITES.search(command):
                action.kind = "file_read"
    elif "send" in tool:
        action.kind = "send"
    elif "draft" in tool:
        action.kind = "draft"
    else:
        action.kind = "other"

    if action.status == "pending" and not action.output and not action.is_error:
        action.reason = "no result was recorded for this call"
        return action

    action.status, action.reason = "ok", ""
    if action.is_error:
        action.status, action.reason = "failed", "the tool returned an error"
        return action
    for pattern, why in _FAIL_PATTERNS:
        if pattern.search(action.output):
            action.status, action.reason = "failed", why
            return action
    if action.kind == "test" and _TEST_FAILED.search(action.output) and not re.search(r"\b0 failed\b", action.output):
        action.status, action.reason = "failed", "test run reported failures"
        return action
    if action.kind not in ("file_write",) and not action.output.strip():
        action.status, action.reason = "silent", "it printed nothing, so success is not shown"
    return action


def tests_passed(action: Action) -> bool:
    return action.status == "ok" and bool(_TEST_PASSED.search(action.output))
