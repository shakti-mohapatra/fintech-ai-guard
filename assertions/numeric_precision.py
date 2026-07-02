"""promptfoo custom assertion: verifies numeric/currency arithmetic in
structured LLM output.

Contract (promptfoo `type: python`): get_assert(output, context) -> dict.
Ground truth is deterministic (docs/test-strategy.md): arithmetic is
recomputed from the scenario's own `context` and compared to the model's
output within a currency-aware epsilon (cents, not floats). Two
independent checks run when their inputs are present:
  - `expected_total` / `total_field`: output[total_field] must equal the
    scenario's precomputed correct total.
  - `components` / `total_field`: output[total_field] must equal the sum
    of output[c] for c in components — catches a total that's internally
    inconsistent with the model's own stated breakdown, even when no
    external expected_total is given.
Also reused by L3-extraction scenarios (docs/test-strategy.md category 8)
for their tax/total reconciliation check.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _json_utils import strip_markdown_fences  # noqa: E402

EPSILON = 0.005  # half a cent — catches any full-cent discrepancy while tolerating float noise


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= EPSILON


def get_assert(output: str, context: dict) -> dict:
    variables = context.get("vars", {})
    ctx = variables.get("context", {}) or {}

    try:
        parsed = json.loads(strip_markdown_fences(output))
    except json.JSONDecodeError as e:
        return {"pass": False, "score": 0.0, "reason": f"Model output is not valid JSON: {e}"}

    total_field = ctx.get("total_field", "total_amount")
    has_expected_total = "expected_total" in ctx
    components = ctx.get("components")

    if not has_expected_total and not components:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "Scenario context is missing both 'expected_total' and 'components' — nothing to check.",
        }

    actual = parsed.get(total_field)
    if not isinstance(actual, (int, float)):
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Output field '{total_field}' is missing or not numeric.",
        }

    if has_expected_total:
        expected = ctx["expected_total"]
        if not _close(actual, expected):
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"'{total_field}' is {actual}, expected {expected} (off by {abs(actual - expected):.2f}).",
            }

    if components:
        missing = [c for c in components if not isinstance(parsed.get(c), (int, float))]
        if missing:
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Output is missing numeric component field(s): {missing}.",
            }
        component_sum = sum(parsed[c] for c in components)
        if not _close(component_sum, actual):
            return {
                "pass": False,
                "score": 0.0,
                "reason": (
                    f"Components {components} sum to {component_sum:.2f} but '{total_field}' is {actual} "
                    f"(off by {abs(component_sum - actual):.2f})."
                ),
            }

    return {"pass": True, "score": 1.0, "reason": "Numeric output reconciles with scenario arithmetic."}
