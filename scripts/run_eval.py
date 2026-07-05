"""Local convenience wrapper around `promptfoo eval`: runs the real eval
config, writes the raw JSON export to reports/raw/, then calls
scripts/generate_report.py to produce the curated markdown snapshot and
refresh evaluation_report.md.

Pure convenience — no gating logic lives here. PROMPTFOO_PASS_RATE_THRESHOLD
already gates natively (docs/plan.md); this script's exit code mirrors
`promptfoo eval`'s own so it still works as a CI/pre-push gate on its own.

Any extra CLI args pass straight through to `promptfoo eval` — e.g.
`python scripts/run_eval.py --filter-first-n 5` to cap request count
against a free-tier quota (see PROGRESS.md's Sprint 4/Sprint 3-close-out
quota findings: gemini-2.5-flash caps at 20 requests/day).
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "reports" / "raw"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ts_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = RAW_DIR / f"eval-{ts_slug}.json"

    npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"
    eval_cmd = [npx_cmd, "promptfoo", "eval", "-c", "promptfooconfig.js", "-o", str(raw_path), *argv]
    print(f"Running: {' '.join(eval_cmd)}")
    eval_result = subprocess.run(eval_cmd, cwd=REPO_ROOT)

    if not raw_path.exists():
        print(
            f"No output written to {raw_path} — promptfoo eval likely failed before producing results.",
            file=sys.stderr,
        )
        return eval_result.returncode or 1

    report_cmd = [sys.executable, str(REPO_ROOT / "scripts" / "generate_report.py"), str(raw_path)]
    report_result = subprocess.run(report_cmd, cwd=REPO_ROOT)
    if report_result.returncode != 0:
        return report_result.returncode

    # Mirror promptfoo eval's own exit code (e.g. 100 on a
    # PROMPTFOO_PASS_RATE_THRESHOLD breach) so this still works as a gate.
    return eval_result.returncode


if __name__ == "__main__":
    sys.exit(main())
