"""Plain data types shared by the parser, the claim extractor and the checker."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Action:
    """One tool call the agent made, and what came back."""

    index: int
    tool: str
    input: dict
    output: str = ""
    is_error: bool = False
    kind: str = "other"          # file_write, file_read, command, test, git_commit, git_push, ...
    status: str = "ok"           # ok | failed | silent (no output) | pending (no result recorded)
    reason: str = ""             # why it was judged failed / silent

    def text(self) -> str:
        """Everything about the call that a claim could refer to."""
        return " ".join(str(v) for v in self.input.values()) + " " + self.output

    def label(self) -> str:
        for key in ("command", "file_path", "path", "pattern", "url", "query"):
            if key in self.input:
                value = str(self.input[key]).replace("\n", " ")
                return f"{self.tool}: {value[:90]}"
        return self.tool


@dataclass
class Turn:
    """One user request and everything the agent did until its final reply."""

    index: int
    prompt: str
    actions: list[Action] = field(default_factory=list)
    summary: str = ""
    cwd: str = ""


@dataclass
class Claim:
    text: str
    kind: str
    targets: list[str] = field(default_factory=list)


@dataclass
class Finding:
    claim: Claim
    verdict: str                  # verified | unverified | contradicted
    reason: str
    evidence: list[Action] = field(default_factory=list)


@dataclass
class Report:
    turn: Turn
    findings: list[Finding]
    unreported_failures: list[Action]

    @property
    def contradicted(self) -> list[Finding]:
        return [f for f in self.findings if f.verdict == "contradicted"]

    @property
    def unverified(self) -> list[Finding]:
        return [f for f in self.findings if f.verdict == "unverified"]

    @property
    def clean(self) -> bool:
        return not self.contradicted and not self.unreported_failures
