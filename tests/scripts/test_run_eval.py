"""Unit tests for scripts/run_eval.py. subprocess.run is monkeypatched
throughout — this wrapper's job is plumbing (build the promptfoo command,
locate the raw export, hand off to generate_report.py, propagate the exit
code), not anything worth spending a real eval run to verify.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

import run_eval  # noqa: E402


def test_builds_expected_promptfoo_command(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "RAW_DIR", tmp_path)
    captured = []

    def fake_run(cmd, cwd=None):
        captured.append(cmd)
        # Simulate promptfoo writing its -o output file.
        if cmd[0] == "npx":
            out_path = Path(cmd[cmd.index("-o") + 1])
            out_path.write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_eval.subprocess, "run", fake_run)
    run_eval.main([])

    eval_cmd = captured[0]
    assert eval_cmd[:5] == ["npx", "promptfoo", "eval", "-c", "promptfooconfig.js"]
    assert "-o" in eval_cmd


def test_extra_args_are_passed_through_to_promptfoo(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "RAW_DIR", tmp_path)
    captured = []

    def fake_run(cmd, cwd=None):
        captured.append(cmd)
        if cmd[0] == "npx":
            out_path = Path(cmd[cmd.index("-o") + 1])
            out_path.write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_eval.subprocess, "run", fake_run)
    run_eval.main(["--filter-first-n", "5"])

    eval_cmd = captured[0]
    assert "--filter-first-n" in eval_cmd
    assert "5" in eval_cmd


def test_calls_generate_report_with_raw_path(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "RAW_DIR", tmp_path)
    captured = []

    def fake_run(cmd, cwd=None):
        captured.append(cmd)
        if cmd[0] == "npx":
            out_path = Path(cmd[cmd.index("-o") + 1])
            out_path.write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_eval.subprocess, "run", fake_run)
    run_eval.main([])

    report_cmd = captured[1]
    assert "generate_report.py" in report_cmd[1]


def test_returns_eval_exit_code_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "RAW_DIR", tmp_path)

    def fake_run(cmd, cwd=None):
        if cmd[0] == "npx":
            out_path = Path(cmd[cmd.index("-o") + 1])
            out_path.write_text("{}", encoding="utf-8")
            return SimpleNamespace(returncode=100)  # e.g. PROMPTFOO_PASS_RATE_THRESHOLD breach
        return SimpleNamespace(returncode=0)  # generate_report.py succeeded

    monkeypatch.setattr(run_eval.subprocess, "run", fake_run)
    exit_code = run_eval.main([])
    assert exit_code == 100


def test_skips_report_generation_when_promptfoo_produced_no_output(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "RAW_DIR", tmp_path)
    calls = []

    def fake_run(cmd, cwd=None):
        calls.append(cmd)
        return SimpleNamespace(returncode=1)  # promptfoo failed, no -o file written

    monkeypatch.setattr(run_eval.subprocess, "run", fake_run)
    exit_code = run_eval.main([])

    assert exit_code == 1
    assert len(calls) == 1, "generate_report.py must not be invoked when promptfoo wrote no output"


def test_returns_report_exit_code_when_report_generation_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "RAW_DIR", tmp_path)

    def fake_run(cmd, cwd=None):
        if cmd[0] == "npx":
            out_path = Path(cmd[cmd.index("-o") + 1])
            out_path.write_text("{}", encoding="utf-8")
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=2)  # generate_report.py itself errored

    monkeypatch.setattr(run_eval.subprocess, "run", fake_run)
    exit_code = run_eval.main([])
    assert exit_code == 2
