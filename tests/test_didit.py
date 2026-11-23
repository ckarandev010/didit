import json

from didit import check_turn, extract, load
from didit.cli import main

from helpers import call, say, session, user


def verdicts(path):
    report = check_turn(load(path)[-1])
    return {f.claim.text: f.verdict for f in report.findings}, report


# ---------- claim extraction ----------

def test_extracts_agent_claims_and_skips_plans_questions_and_explanations():
    text = """Done. I updated `config.py` and all 12 tests pass.
- Committed the change.
Want me to push it?
I'll add docs next.
The parser reads each line as JSON.
I couldn't reach the server."""
    claims = extract(text)
    assert {c.kind for c in claims} >= {"file_write", "test", "git_commit"}
    texts = " ".join(c.text for c in claims)
    assert "push it" not in texts and "add docs" not in texts
    assert "parser reads" not in texts and "couldn't" not in texts


def test_targets_come_from_backticks_paths_and_links():
    [claim] = extract("I saved the report to `out/report.md` and linked [the doc](https://example.com/doc/1).")
    assert "out/report.md" in claim.targets
    assert "https://example.com/doc/1" in claim.targets


def test_quoted_speech_is_not_a_claim():
    assert extract('If they ask, say "I built the whole data pipeline myself".') == []


# ---------- verdicts ----------

def test_verified_when_the_write_succeeded(tmp_path):
    path = session(tmp_path,
                   user("add a helper"),
                   call("Write", {"file_path": "/tmp/project/util.py", "content": "x=1"}, "File created successfully"),
                   say("I created `util.py` with the helper."))
    v, report = verdicts(path)
    assert list(v.values()) == ["verified"]
    assert report.clean


def test_contradicted_when_tests_failed_but_summary_says_they_pass(tmp_path):
    path = session(tmp_path,
                   user("fix the bug"),
                   call("Bash", {"command": "pytest -q"}, "2 failed, 10 passed in 0.4s\nExit code 1"),
                   say("Fixed it. All tests pass."))
    v, report = verdicts(path)
    assert "contradicted" in v.values()


def test_test_claim_verified_by_a_passing_run(tmp_path):
    path = session(tmp_path,
                   user("run tests"),
                   call("Bash", {"command": "pytest -q"}, "12 passed in 0.3s"),
                   say("All 12 tests pass."))
    v, _ = verdicts(path)
    assert list(v.values()) == ["verified"]


def test_unverified_when_claimed_push_never_happened(tmp_path):
    path = session(tmp_path,
                   user("commit and push"),
                   call("Bash", {"command": "git commit -m 'fix'"}, "[main abc123] fix\n 1 file changed"),
                   say("I committed the fix and pushed it to GitHub."))
    report = check_turn(load(path)[-1])
    by_kind = {f.claim.kind: f.verdict for f in report.findings}
    assert by_kind == {"git_commit": "verified", "git_push": "unverified"}


def test_contradicted_when_push_was_rejected(tmp_path):
    path = session(tmp_path,
                   user("push"),
                   call("Bash", {"command": "git push origin main"}, " ! [rejected] main -> main (fetch first)\nerror: failed to push"),
                   say("I pushed the branch to origin."))
    v, _ = verdicts(path)
    assert list(v.values()) == ["contradicted"]


def test_silent_command_is_unverified_not_verified(tmp_path):
    path = session(tmp_path,
                   user("mark it done"),
                   call("Bash", {"command": "python tracker.py set row7 Status=Done"}, ""),
                   say("I marked row 7 as Done in `tracker.py`."))
    v, _ = verdicts(path)
    assert list(v.values()) == ["unverified"]


def test_claim_about_a_file_nobody_touched(tmp_path):
    path = session(tmp_path,
                   user("update both files"),
                   call("Edit", {"file_path": "/tmp/project/a.py", "old_string": "1", "new_string": "2"}, "updated"),
                   say("I updated `a.py` and `b.py`."))
    report = check_turn(load(path)[-1])
    assert report.findings[0].verdict == "verified"   # a.py was touched; b.py is a known limitation per sentence
    path2 = session(tmp_path,
                    user("update b"),
                    call("Edit", {"file_path": "/tmp/project/a.py", "old_string": "1", "new_string": "2"}, "updated"),
                    say("I updated `b.py`."))
    v, _ = verdicts(path2)
    assert list(v.values()) == ["unverified"]


def test_failed_call_not_mentioned_in_summary_is_reported(tmp_path):
    path = session(tmp_path,
                   user("deploy"),
                   call("Bash", {"command": "scp app.tar server:/srv"}, "Permission denied (publickey)."),
                   say("Deployment steps are complete."))
    _, report = verdicts(path)
    assert len(report.unreported_failures) == 1


def test_failure_that_was_retried_successfully_is_not_reported(tmp_path):
    path = session(tmp_path,
                   user("install deps"),
                   call("Bash", {"command": "pip install requests"}, "error: externally-managed-environment\nExit code 1"),
                   call("Bash", {"command": "pip install --user requests"}, "Successfully installed requests"),
                   say("I installed requests."))
    v, report = verdicts(path)
    assert report.unreported_failures == []
    assert list(v.values()) == ["verified"]


def test_admitted_failure_is_not_double_reported(tmp_path):
    path = session(tmp_path,
                   user("deploy"),
                   call("Bash", {"command": "scp app.tar server:/srv"}, "Permission denied (publickey)."),
                   say("The upload failed: the server rejected the SSH key."))
    _, report = verdicts(path)
    assert report.unreported_failures == []


# ---------- loading ----------

def test_turns_split_on_human_messages(tmp_path):
    path = session(tmp_path,
                   user("first"), say("Hi."),
                   user("second"), call("Bash", {"command": "ls"}, "a.py"), say("Listed the files."))
    turns = load(path)
    assert [t.prompt for t in turns] == ["first", "second"]
    assert len(turns[1].actions) == 1


def test_simple_json_format(tmp_path):
    p = tmp_path / "run.json"
    p.write_text(json.dumps({"prompt": "build", "summary": "I built the project.",
                             "actions": [{"tool": "shell", "input": {"command": "make"}, "output": "make: *** Error 2\nExit code 2"}]}))
    report = check_turn(load(p)[0])
    assert report.findings[0].verdict == "contradicted"


# ---------- cli ----------

def test_cli_exit_code_is_1_on_contradiction(tmp_path, capsys):
    path = session(tmp_path,
                   user("test"),
                   call("Bash", {"command": "pytest"}, "1 failed\nExit code 1"),
                   say("All tests pass."))
    assert main(["check", path]) == 1
    assert "CONTRADICTED" in capsys.readouterr().out


def test_hook_is_silent_when_clean_and_never_loops(tmp_path, monkeypatch, capsys):
    import io
    path = session(tmp_path,
                   user("test"),
                   call("Bash", {"command": "pytest"}, "1 failed\nExit code 1"),
                   say("All tests pass."))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"transcript_path": path, "stop_hook_active": True})))
    assert main(["hook", "--strict"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"transcript_path": path})))
    assert main(["hook", "--strict"]) == 2
    assert "does not match" in capsys.readouterr().err
