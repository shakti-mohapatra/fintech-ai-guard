"""Unit tests for scripts/generate_report.py. Uses hand-built promptfoo
export fixtures matching the real shape (confirmed against a live smoke
run's JSON output and against the installed promptfoo package's own
ResultFailureReason enum in tables-*.cjs) rather than a live eval — no
API calls, no quota spent.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

import generate_report as gr  # noqa: E402


def _result(category, failure_reason, latency_ms, provider="google:gemini-2.5-flash"):
    return {
        "vars": {"category": category},
        "provider": {"id": provider},
        "success": failure_reason == gr.FAILURE_REASON_NONE,
        "failureReason": failure_reason,
        "latencyMs": latency_ms,
    }


def _export(results, successes, failures, errors, timestamp="2026-07-03T00:00:00Z"):
    return {
        "results": {
            "timestamp": timestamp,
            "stats": {"successes": successes, "failures": failures, "errors": errors},
            "results": results,
        }
    }


def test_compute_metrics_buckets_pass_fail_error_correctly():
    results = [
        _result("hallucination", gr.FAILURE_REASON_NONE, 100),
        _result("hallucination", gr.FAILURE_REASON_ASSERT, 150),
        _result("hallucination", gr.FAILURE_REASON_ERROR, 50),
    ]
    export = _export(results, successes=1, failures=1, errors=1)
    metrics = gr.compute_metrics(export)

    bucket = metrics["by_category"]["hallucination"]
    assert bucket == {"total": 3, "passed": 1, "failed": 1, "errored": 1}


def test_composite_pass_rate_uses_top_level_stats():
    results = [_result("hallucination", gr.FAILURE_REASON_NONE, 100)] * 3
    export = _export(results, successes=3, failures=1, errors=0)
    metrics = gr.compute_metrics(export)
    # 3 successes / (3 successes + 1 failure + 0 errors) = 75%
    assert metrics["composite_pass_rate"] == 75.0


def test_composite_pass_rate_is_none_when_no_tests():
    export = _export([], successes=0, failures=0, errors=0)
    metrics = gr.compute_metrics(export)
    assert metrics["composite_pass_rate"] is None


def test_latency_percentiles_computed_from_results():
    results = [_result("hallucination", gr.FAILURE_REASON_NONE, ms) for ms in [10, 20, 30, 40, 100]]
    export = _export(results, successes=5, failures=0, errors=0)
    metrics = gr.compute_metrics(export)
    assert metrics["latency_p50_ms"] == 30
    # n=5, k=(5-1)*0.95=3.8 -> interpolate between sorted[3]=40 and sorted[4]=100
    assert metrics["latency_p95_ms"] == pytest.approx(88.0)


def test_latency_is_none_when_no_timed_results():
    export = _export([], successes=0, failures=0, errors=0)
    metrics = gr.compute_metrics(export)
    assert metrics["latency_p50_ms"] is None
    assert metrics["latency_p95_ms"] is None


def test_providers_deduplicated_and_sorted():
    results = [
        _result("hallucination", gr.FAILURE_REASON_NONE, 10, provider="google:gemini-2.5-flash"),
        _result("hallucination", gr.FAILURE_REASON_NONE, 10, provider="anthropic:messages:claude-sonnet-5"),
        _result("hallucination", gr.FAILURE_REASON_NONE, 10, provider="google:gemini-2.5-flash"),
    ]
    export = _export(results, successes=3, failures=0, errors=0)
    metrics = gr.compute_metrics(export)
    assert metrics["providers"] == ["anthropic:messages:claude-sonnet-5", "google:gemini-2.5-flash"]


def test_render_markdown_marks_absent_category_as_not_run():
    export = _export(
        [_result("hallucination", gr.FAILURE_REASON_NONE, 10)], successes=1, failures=0, errors=0
    )
    metrics = gr.compute_metrics(export)
    report = gr.render_markdown(metrics)
    assert "| Prompt-Injection Resistance Rate | `injection` | 0 | - | - | - | not run |" in report


def test_render_markdown_all_errored_category_reports_no_rate_not_zero():
    export = _export(
        [_result("hallucination", gr.FAILURE_REASON_ERROR, 10)], successes=0, failures=0, errors=1
    )
    metrics = gr.compute_metrics(export)
    report = gr.render_markdown(metrics)
    assert "all errored, no rate" in report
    # Must not silently render an error-only category as a 0% or 100% rate.
    assert "| Hallucination Rate | `hallucination` | 1 | 0 | 0 | 1 | 0.0% |" not in report


def test_render_markdown_error_direction_metric_inverts_pass_rate():
    # hallucination is an "error" direction metric: value = 100 - pass_rate.
    results = [_result("hallucination", gr.FAILURE_REASON_ASSERT, 10)] * 1 + [
        _result("hallucination", gr.FAILURE_REASON_NONE, 10)
    ] * 3
    export = _export(results, successes=3, failures=1, errors=0)
    metrics = gr.compute_metrics(export)
    report = gr.render_markdown(metrics)
    # 3 passed / 4 gradeable = 75% pass -> Hallucination Rate = 25.0%
    assert "25.0%" in report


def test_render_markdown_includes_not_yet_measured_section():
    export = _export([], successes=0, failures=0, errors=0)
    metrics = gr.compute_metrics(export)
    report = gr.render_markdown(metrics)
    assert "## Not Yet Measured" in report
    assert "Cross-Run Consistency" in report
    assert "Authorization-Boundary Integrity" in report


def test_main_writes_snapshot_and_refreshes_evaluation_report(tmp_path, monkeypatch):
    export = _export(
        [_result("schema-compliance", gr.FAILURE_REASON_NONE, 10)], successes=1, failures=0, errors=0
    )
    export_path = tmp_path / "raw.json"
    export_path.write_text(__import__("json").dumps(export), encoding="utf-8")

    fake_reports_dir = tmp_path / "reports"
    fake_repo_root = tmp_path

    monkeypatch.setattr(gr, "REPORTS_DIR", fake_reports_dir)
    monkeypatch.setattr(gr, "REPO_ROOT", fake_repo_root)
    monkeypatch.setattr(gr, "_git_sha", lambda: "abc1234")

    exit_code = gr.main([str(export_path)])
    assert exit_code == 0

    snapshots = list(fake_reports_dir.glob("eval-*-abc1234.md"))
    assert len(snapshots) == 1
    assert (fake_repo_root / "evaluation_report.md").exists()
    assert "Schema Validation Pass Rate" in (fake_repo_root / "evaluation_report.md").read_text(encoding="utf-8")


def test_main_with_no_args_returns_error():
    assert gr.main([]) == 1
