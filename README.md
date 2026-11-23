# didit

**Did the agent actually do it?**

AI coding agents finish a task with a confident summary: *"Fixed the bug, all tests pass, committed and pushed."*
Sometimes part of that is not true. A test run failed, a `git push` was rejected, a command printed nothing,
or a file the summary mentions was never touched. Nobody checks the summary against what really happened.

`didit` does. It reads an agent session, pulls every claim out of the agent's final message, and checks each one
against the agent's own tool calls and their results.

```
$ didit check ~/.claude/projects/my-project/
Turn 12: fix the login bug and push
  9 tool calls, 4 claims checked
  ✗ CONTRADICTED  All tests pass.
      why: the last test run failed (test run reported failures)
      call #6: Bash: pytest -q
  ? UNVERIFIED  Committed the fix and pushed it to GitHub.
      why: no git push tool call in this turn
  2 verified · 1 unverified · 1 contradicted · 0 unreported failures
```

## Verdicts

| Verdict | Meaning |
|---|---|
| ✓ verified | A matching tool call ran and succeeded. |
| ? unverified | Nothing in the session backs the claim up: no matching call, a call with no output, or no result recorded. |
| ✗ contradicted | The matching call failed: an error, a non-zero exit code, failing tests, a rejected push, an edit that did not apply. |

It also reports **failed calls the summary never mentions**: errors the agent hit and quietly moved past.

## How it works

No model is needed. Everything is plain, testable rules, so it runs offline and gives the same answer every time.

1. **Parse** the session into turns: one human request, the tool calls that followed, and the agent's final message.
2. **Classify each tool call** (file write, shell command, test run, git commit, git push, install, delete...) and
   decide whether it worked from the tool's error flag, exit codes, tracebacks, test counts and known failure text.
3. **Extract claims** from the final message: sentences where the agent says it did something ("I updated
   `config.py`", "Committed and pushed", "All 12 tests pass"). Plans, offers, questions, quoted speech and admitted
   failures are skipped. A sentence like "committed and pushed" becomes two claims.
4. **Match and judge**: link each claim to the calls that could support it (by kind and by the files, commands or
   links it names) and give a verdict. A failure that was retried successfully does not count against the agent.

## Install

```
pip install git+https://github.com/ckarandev010/didit
```

Python 3.10+, no dependencies.

## Use

```
didit check SESSION.jsonl            # check the last turn
didit check SESSION.jsonl --all      # every turn, show only the ones with problems
didit check PROJECT_FOLDER/          # newest session in a folder
didit check SESSION.jsonl --turn 7 --verbose   # one turn, including verified claims
didit check SESSION.jsonl --json     # machine-readable
didit check SESSION.jsonl --check-files        # also confirm claimed files still exist
```

Exit code is `1` when anything is contradicted or a failure went unreported, so it can gate CI.

### As a Claude Code hook

Run `didit` automatically every time the agent finishes. Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [{ "hooks": [{ "type": "command", "command": "didit hook --strict" }] }]
  }
}
```

With `--strict`, a summary that does not match the tool calls is sent back to the agent to correct before it stops.
Without it, problems are only printed. It never blocks twice in a row, so it cannot loop.

### Other agents

Claude Code session logs (`~/.claude/projects/<project>/<session>.jsonl`) are read directly. For any other agent,
write the run in this neutral format and point `didit` at the `.json` file:

```json
{
  "prompt": "fix the build",
  "summary": "I fixed the import and the build passes.",
  "actions": [
    {"tool": "shell", "input": {"command": "make"}, "output": "make: *** [all] Error 2\nExit code 2", "error": false}
  ]
}
```

## Benchmark

**Synthetic** ([full results](bench/RESULTS.md)): 180 generated agent turns with known truth, 150 claims (half true,
half false) across tests, commits, pushes, file edits and installs. Phrasings deliberately include ones the rules
are not built to recognise.

| | v0.1 |
|---|---|
| False claims caught, of those it extracted | **100%** |
| False alarms on true claims | **0%** |
| `contradicted` verdicts that were really false | **100%** |
| Claims extracted at all (extraction recall) | 68% |
| Silent failures reported / admitted failures wrongly reported | 15/15 · 0/15 |

The weak spot is extraction: claims phrased without an agent verb ("The changes are now on GitHub",
"`app.py` now handles the empty case") are not picked up yet. Reproduce with:

```
python bench/synthetic.py && python bench/run.py
```

Writing the benchmark found two real bugs, now fixed with regression tests: "45 passed, 0 failed" was skipped as an
admitted failure, and reading a file (`cat README.md`) counted as evidence it had been changed.

**Real sessions**: `bench/real.py` samples claims from your own session logs into a private, git-ignored sheet to
label by hand, then scores it. Only the aggregate numbers are published. On one long personal session
(1,388 turns), v0.1 checked 468 claims and found 98 failed calls the summaries never mentioned; labelled results
will be added here.

## Limits (v0.1)

- Claim extraction is rule-based English. It misses claims phrased unusually and sometimes flags narrative
  sentences as claims.
- A claim is matched by kind and by the names it mentions. It cannot tell *what* an edit changed, only that a
  matching edit succeeded.
- Work done through tools that return nothing (or through other tools' side effects) shows as unverified.
- Session logs contain private data. Never commit them; the tests here use synthetic sessions only.

## Roadmap

- Labelled benchmark of real claims with precision and recall published here.
- Optional local-model claim extraction (Ollama) for claims rules miss.
- Readers for more agent log formats (Codex CLI, Cursor, OpenAI Agents SDK traces).
- Content checks: "renamed X to Y" confirmed against the actual diff.

## Development

```
pip install -e ".[dev]"
pytest
```

## License

MIT
