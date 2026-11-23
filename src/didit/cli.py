"""didit command line.

  didit check SESSION [--turn N | --all] [--json] [--verbose] [--check-files]
  didit hook [--strict]        # Claude Code Stop hook: reads the hook payload on stdin
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .check import check_turn
from .report import to_json, to_text
from .transcript import load


def _cmd_check(args) -> int:
    turns = [t for t in load(args.session) if t.actions or t.summary]
    if not turns:
        print("No agent turns found in that session.", file=sys.stderr)
        return 2
    if args.all:
        chosen = turns
    elif args.turn is not None:
        chosen = [t for t in turns if t.index == args.turn]
        if not chosen:
            print(f"No turn {args.turn}. Turns available: 0-{turns[-1].index}", file=sys.stderr)
            return 2
    else:
        chosen = [turns[-1]]

    reports = [check_turn(t, check_files=args.check_files) for t in chosen]
    if args.all and not args.verbose:
        reports = [r for r in reports if not r.clean or r.unverified] or reports[-1:]
    if args.json:
        print(to_json(reports))
    else:
        print("\n\n".join(to_text(r, verbose=args.verbose) for r in reports))
    return 1 if any(r.contradicted or r.unreported_failures for r in reports) else 0


def _cmd_hook(args) -> int:
    """Run as a Claude Code Stop hook. Exit 2 (strict) sends the problems back to the agent."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("stop_hook_active"):        # already continuing because of us: never loop
        return 0
    path = payload.get("transcript_path")
    if not path:
        return 0
    try:
        turns = [t for t in load(path) if t.actions]
    except (OSError, ValueError):
        return 0
    if not turns:
        return 0
    report = check_turn(turns[-1])
    if report.clean and not (args.strict and report.unverified):
        return 0
    problems = [f"- {f.verdict}: \"{f.claim.text}\" ({f.reason})" for f in report.contradicted]
    problems += [f"- failed call #{a.index} not mentioned: {a.label()} ({a.reason})" for a in report.unreported_failures]
    if args.strict:
        problems += [f"- unverified: \"{f.claim.text}\" ({f.reason})" for f in report.unverified]
    print("didit: your summary does not match your tool calls:\n" + "\n".join(problems) +
          "\nCheck these and correct the summary.", file=sys.stderr)
    return 2 if args.strict else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="didit", description="Check an AI agent's summary against what its tools did.")
    parser.add_argument("--version", action="version", version=f"didit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="check a session file (or the newest session in a folder)")
    p.add_argument("session")
    p.add_argument("--turn", type=int, help="turn number to check (default: the last one)")
    p.add_argument("--all", action="store_true", help="check every turn, show only those with problems")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--verbose", "-v", action="store_true", help="also show verified claims")
    p.add_argument("--check-files", action="store_true", help="confirm claimed files still exist on disk")
    p.set_defaults(func=_cmd_check)

    h = sub.add_parser("hook", help="run as a Claude Code Stop hook (reads JSON on stdin)")
    h.add_argument("--strict", action="store_true", help="block the stop and send problems back to the agent")
    h.set_defaults(func=_cmd_hook)

    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
