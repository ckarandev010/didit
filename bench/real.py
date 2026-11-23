"""Benchmark didit on your own real agent sessions, privately.

1. sample:  python bench/real.py sample SESSION.jsonl [SESSION2.jsonl ...] --n 100
            -> bench/private/labels.csv   (git-ignored: it quotes your sessions)
2. label:   open the CSV and fill the `truth` column for each row:
              true          the claim is correct (the agent really did it)
              false         the claim is wrong (it did not happen, or it failed)
              not_a_claim   the sentence is not a claim of finished work
            Use the `calls` column (the turn's tool calls, with status) to decide.
3. score:   python bench/real.py score   -> prints metrics you can publish (no session content)
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "src"))

from didit.check import check_turn  # noqa: E402
from didit.transcript import load  # noqa: E402

PRIVATE = HERE / "private"
LABELS = PRIVATE / "labels.csv"
FIELDS = ["id", "session", "turn", "prompt", "claim", "kind", "didit_verdict", "didit_reason", "calls", "truth", "notes"]


def sample(paths, n, seed):
    rows = []
    for path in paths:
        for turn in load(path):
            if not turn.actions and not turn.summary:
                continue
            report = check_turn(turn)
            calls = " || ".join(f"#{a.index} [{a.status}] {a.label()[:120]}" for a in turn.actions[:25])
            for f in report.findings:
                rows.append({"session": Path(path).stem[:8], "turn": turn.index, "prompt": turn.prompt[:200],
                             "claim": f.claim.text, "kind": f.claim.kind, "didit_verdict": f.verdict,
                             "didit_reason": f.reason, "calls": calls, "truth": "", "notes": ""})
    rng = random.Random(seed)
    # Stratify so the rare verdicts are represented: up to a third each.
    by_verdict = {}
    for r in rows:
        by_verdict.setdefault(r["didit_verdict"], []).append(r)
    for pool in by_verdict.values():
        rng.shuffle(pool)
    picked = by_verdict.get("contradicted", [])[: n // 3] + by_verdict.get("unverified", [])[: n // 3]
    picked += by_verdict.get("verified", [])[: n - len(picked)]
    rng.shuffle(picked)
    for i, r in enumerate(picked):
        r["id"] = f"r{i:03d}"
    PRIVATE.mkdir(exist_ok=True)
    with open(LABELS, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, FIELDS)
        w.writeheader()
        w.writerows(picked)
    print(f"{len(rows)} claims found; wrote {len(picked)} to {LABELS} "
          f"({Counter(r['didit_verdict'] for r in picked)})")


def score():
    with open(LABELS, encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh) if r["truth"].strip()]
    if not rows:
        print("No labelled rows yet: fill the `truth` column first.")
        return
    truth = Counter(r["truth"].strip() for r in rows)
    claims = [r for r in rows if r["truth"].strip() in ("true", "false")]
    false_claims = [r for r in claims if r["truth"].strip() == "false"]
    true_claims = [r for r in claims if r["truth"].strip() == "true"]
    flagged = lambda rs: sum(r["didit_verdict"] != "verified" for r in rs)  # noqa: E731
    contradicted = [r for r in claims if r["didit_verdict"] == "contradicted"]
    print(f"Labelled rows: {len(rows)}  ({dict(truth)})")
    print(f"Extraction precision (rows that really are claims): {len(claims)}/{len(rows)}")
    print(f"Catch rate (false claims flagged): {flagged(false_claims)}/{len(false_claims)}")
    print(f"False alarm rate (true claims flagged): {flagged(true_claims)}/{len(true_claims)}")
    print(f"Contradiction precision: {sum(r['truth'].strip() == 'false' for r in contradicted)}/{len(contradicted)}")
    print("Note: rows were sampled stratified by verdict, so rates describe these rows, not the session mix.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("sessions", nargs="+")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, default=1)
    sub.add_parser("score")
    args = ap.parse_args()
    if args.cmd == "sample":
        sample(args.sessions, args.n, args.seed)
    else:
        score()


if __name__ == "__main__":
    main()
