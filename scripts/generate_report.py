"""Computes the QA metrics table from a promptfoo JSON eval export and
writes a timestamped snapshot into reports/, then refreshes the
repo-root evaluation_report.md copy (see docs/plan.md's repo structure —
"auto-regenerated copy of latest reports/*.md").

Usage: python scripts/generate_report.py <promptfoo_output.json>

Reads a JSON file produced by `promptfoo eval -o <path>.json` (see
scripts/run_eval.py, which produces this automatically). Makes no API
calls and runs no eval itself — pure reporting, per the architecture
decision in docs/plan.md ("PROMPTFOO_PASS_RATE_THRESHOLD (native, exits
100 on breach) — custom scripts stay pure reporting, not gating logic").

Per-result grading distinguishes an assertion *failure* from a transport
*error* using promptfoo's own ResultFailureReason enum (NONE=0, ASSERT=1,
ERROR=2 — confirmed against the installed promptfoo package's own
tables-*.cjs, not guessed) so a provider-side 503 doesn't get counted as
a model-quality finding, same distinction PROGRESS.md's Sprint 4 entry
flagged promptfoo already makes at the top-level stats.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports"

FAILURE_REASON_NONE = 0
FAILURE_REASON_ASSERT = 1
FAILURE_REASON_ERROR = 2

# category -> (QA metric name, "pass" if a higher pass-rate is the good
# direction, "error" if the metric is conventionally phrased as an error
# rate, i.e. 100 - pass_rate) — see docs/plan.md § QA Metrics.
_CATEGORY_METRICS = {
    "hallucination": ("Hallucination Rate", "error"),
    "injection": ("Prompt-Injection Resistance Rate", "pass"),
    "schema-compliance": ("Schema Validation Pass Rate", "pass"),
    "numeric-precision": ("Numeric Precision Error Rate", "error"),
    "logic-consistency": ("Business-Logic Consistency Rate", "pass"),
    "idempotency": ("Idempotency Handling Rate", "pass"),
    "pii-pci": ("PII/PCI Leakage Rate", "error"),
    "l3-data-extraction": ("L3 Extraction Accuracy Rate", "pass"),
    "tone-disclosure": ("Tone & Disclosure Compliance Score", "pass"),
}

# Metrics docs/plan.md lists that this script cannot compute from a single
# eval export, and why — named explicitly so the report says so rather
# than omitting them silently or inventing a number (docs/plan.md's
# verification checklist requires "real numbers, not placeholders").
_NOT_YET_MEASURED = [
    (
        "Authorization-Boundary Integrity",
        "needs promptfoo redteam BFLA/BOLA plugins against mock_api/ (Sprint 8)",
    ),
    (
        "Explainability / Reason-Code Completeness",
        "no assertion yet checks reason-code presence/quality specifically",
    ),
    (
        "Cross-Run Consistency",
        "needs multiple runs (temp=0 determinism vs. sampled-N semantic consistency) compared against each other, not derivable from one export",
    ),
    (
        "False-Refusal / Over-Blocking Rate",
        "currently only observable within idempotency_check.py's over-blocking direction (docs/test-strategy.md); no cross-category rollup yet",
    ),
]


def _percentile(sorted_values: list, pct: float):
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _git_sha() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()
    except Exception:
        return "unknown"


def load_export(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compute_metrics(export: dict) -> dict:
    inner = export.get("results", {}) or {}
    results = inner.get("results", []) or []
    stats = inner.get("stats", {}) or {}

    providers = sorted({(r.get("provider") or {}).get("id", "unknown") for r in results})

    by_category = {}
    latencies = []
    for r in results:
        v = r.get("vars", {}) or {}
        category = v.get("category", "(uncategorized)")
        bucket = by_category.setdefault(category, {"total": 0, "passed": 0, "failed": 0, "errored": 0})
        bucket["total"] += 1

        reason = r.get("failureReason", FAILURE_REASON_NONE if r.get("success") else FAILURE_REASON_ASSERT)
        if reason == FAILURE_REASON_ERROR:
            bucket["errored"] += 1
        elif reason == FAILURE_REASON_ASSERT:
            bucket["failed"] += 1
        else:
            bucket["passed"] += 1

        latency = r.get("latencyMs")
        if isinstance(latency, (int, float)):
            latencies.append(latency)

    total = stats.get("successes", 0) + stats.get("failures", 0) + stats.get("errors", 0)
    composite_pass_rate = (stats.get("successes", 0) / total * 100) if total else None

    latencies.sort()

    return {
        "providers": providers,
        "total_tests": total,
        "successes": stats.get("successes", 0),
        "failures": stats.get("failures", 0),
        "errors": stats.get("errors", 0),
        "composite_pass_rate": composite_pass_rate,
        "by_category": by_category,
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "timestamp": inner.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
    }


def render_markdown(metrics: dict) -> str:
    lines = [
        "# Evaluation Report — Fintech-AI-Guard",
        "",
        f"- **Timestamp:** {metrics['timestamp']}",
        f"- **Git SHA:** `{metrics['git_sha']}`",
        f"- **Provider(s):** {', '.join(metrics['providers']) or '(none)'}",
        f"- **Total test cases:** {metrics['total_tests']} "
        f"({metrics['successes']} passed, {metrics['failures']} failed, {metrics['errors']} errored)",
        "",
    ]

    if metrics["composite_pass_rate"] is None:
        lines.append("**Composite Compliance Pass Rate:** no test cases in this export.")
    else:
        lines.append(f"**Composite Compliance Pass Rate:** {metrics['composite_pass_rate']:.1f}%")
    lines.append("")

    lines += ["## QA Metrics by Category", "", "| Metric | Category | N | Passed | Failed | Errored | Value |", "|---|---|---|---|---|---|---|"]
    for category, (metric_name, direction) in _CATEGORY_METRICS.items():
        bucket = metrics["by_category"].get(category)
        if not bucket or bucket["total"] == 0:
            lines.append(f"| {metric_name} | `{category}` | 0 | - | - | - | not run |")
            continue
        # Errored cases are excluded from the rate (transport failure, not
        # a model-quality signal) but still shown for visibility.
        gradeable = bucket["passed"] + bucket["failed"]
        if gradeable == 0:
            lines.append(
                f"| {metric_name} | `{category}` | {bucket['total']} | {bucket['passed']} | "
                f"{bucket['failed']} | {bucket['errored']} | all errored, no rate |"
            )
            continue
        pass_rate = bucket["passed"] / gradeable * 100
        value = pass_rate if direction == "pass" else (100 - pass_rate)
        lines.append(
            f"| {metric_name} | `{category}` | {bucket['total']} | {bucket['passed']} | "
            f"{bucket['failed']} | {bucket['errored']} | {value:.1f}% |"
        )
    lines.append("")

    lines += ["## Latency", ""]
    if metrics["latency_p50_ms"] is not None:
        lines.append(f"- p50: {metrics['latency_p50_ms']:.0f} ms")
        lines.append(f"- p95: {metrics['latency_p95_ms']:.0f} ms")
    else:
        lines.append("- not available (no timed results in this export)")
    lines.append("")

    lines += ["## Not Yet Measured", "", "| Metric | Why |", "|---|---|"]
    for name, why in _NOT_YET_MEASURED:
        lines.append(f"| {name} | {why} |")
    lines.append("")

    return "\n".join(lines)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Usage: python scripts/generate_report.py <promptfoo_output.json>", file=sys.stderr)
        return 1

    export_path = Path(argv[0])
    export = load_export(export_path)
    metrics = compute_metrics(export)
    report = render_markdown(metrics)

    REPORTS_DIR.mkdir(exist_ok=True)
    ts_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_path = REPORTS_DIR / f"eval-{ts_slug}-{metrics['git_sha']}.md"
    snapshot_path.write_text(report, encoding="utf-8")
    (REPO_ROOT / "evaluation_report.md").write_text(report, encoding="utf-8")

    print(f"Wrote {snapshot_path}")
    print(f"Refreshed {REPO_ROOT / 'evaluation_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
