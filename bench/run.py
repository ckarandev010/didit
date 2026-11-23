"""Score didit on the synthetic benchmark and write bench/RESULTS.md.

Metrics, from the point of view of someone relying on didit:

* catch rate:      of the FALSE claims, how many did didit flag (unverified or contradicted)?
* false alarm rate: of the TRUE claims, how many did didit flag anyway?
* contradiction precision: when didit says "contradicted", how often is the claim really false?
* extraction recall: of all claims, how many did the extractor find at all?
* unreported-failure detection: silent failures found / admitted failures wrongly reported.

Run:  python bench/synthetic.py && python bench/run.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "src"))

from didit.actions import classify  # noqa: E402
from didit.check import check_turn  # noqa: E402
from didit.models import Action, Turn  # noqa: E402


def to_turn(case) -> Turn:
    turn = Turn(index=0, prompt=case["prompt"], summary=case["summary"])
    for i, a in enumerate(case["actions"]):
        action = Action(index=i, tool=a["tool"], input=a["input"], output=a["output"], is_error=a["error"])
        turn.actions.append(classify(action))
    return turn


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "n/a"


def main():
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    rows = defaultdict(lambda: defaultdict(int))
    misses = []
    spurious = 0
    uf = {"silent_total": 0, "silent_found": 0, "admitted_total": 0, "admitted_flagged": 0}

    for case in cases:
        report = check_turn(to_turn(case))
        found = {f.claim.kind: f for f in report.findings}

        for t in case["truth"]:
            r = rows[t["kind"]]
            key = "true" if t["true"] else "false"
            r[f"{key}_total"] += 1
            f = found.pop(t["kind"], None)
            if f is None:
                r[f"{key}_missed"] += 1
                if t["rule_findable"]:
                    misses.append((case["id"], t["sentence"]))
                continue
            flagged = f.verdict != "verified"
            r[f"{key}_flagged"] += flagged
            r[f"{key}_contradicted"] += f.verdict == "contradicted"
            if not t["true"] and not flagged:
                misses.append((case["id"], f"PASSED A FALSE CLAIM ({t['why_false']}): {t['sentence']}"))
        spurious += len(found)          # claims extracted from sentences that were not claims

        if "unreported_failure" in case:
            if case["unreported_failure"]:
                uf["silent_total"] += 1
                uf["silent_found"] += bool(report.unreported_failures)
            else:
                uf["admitted_total"] += 1
                uf["admitted_flagged"] += bool(report.unreported_failures)

    total = defaultdict(int)
    for r in rows.values():
        for k, v in r.items():
            total[k] += v

    def line(name, r):
        found_false = r["false_total"] - r["false_missed"]
        found_true = r["true_total"] - r["true_missed"]
        claims = r["false_total"] + r["true_total"]
        contradicted = r["false_contradicted"] + r["true_contradicted"]
        return (f"| {name} | {claims} | {pct(r['false_flagged'], r['false_total'])} | "
                f"{pct(r['false_flagged'], found_false)} | {pct(r['true_flagged'], found_true)} | "
                f"{pct(r['false_contradicted'], contradicted)} | {pct(claims - r['false_missed'] - r['true_missed'], claims)} |")

    out = ["# Synthetic benchmark results", "",
           f"{len(cases)} generated agent turns (`bench/synthetic.py`, seed fixed), "
           f"{total['true_total'] + total['false_total']} labelled claims, half true and half false. "
           "Phrasings include ones the rule-based extractor is expected to miss.", "",
           "| Claim kind | Claims | Catch rate (all false claims) | Catch rate (false claims it found) | "
           "False alarms (true claims it found) | Contradiction precision | Extraction recall |",
           "|---|---|---|---|---|---|---|"]
    out += [line(k, rows[k]) for k in sorted(rows)]
    out.append(line("**all**", total))
    out += ["", f"- Non-claim sentences wrongly extracted as claims: {spurious}",
            f"- Silent failures reported: {uf['silent_found']}/{uf['silent_total']}; "
            f"admitted failures wrongly reported: {uf['admitted_flagged']}/{uf['admitted_total']}", "",
            "Definitions: a claim is *caught* when didit marks it unverified or contradicted. "
            "*Catch rate (all)* counts claims the extractor missed as not caught. "
            "*Contradiction precision*: share of `contradicted` verdicts whose claim really was false.", "",
            "This is a synthetic benchmark: it shows how the rules behave on known cases, not how often real "
            "agents make false claims. Results on real sessions are reported separately."]
    if misses:
        out += ["", "## Misses worth fixing", ""] + [f"- `{cid}` {text}" for cid, text in misses[:25]]
    (HERE / "RESULTS.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
