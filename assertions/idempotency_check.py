"""promptfoo custom assertion: verifies duplicate-transaction handling.

Contract (promptfoo `type: python`): get_assert(output, context) -> dict.
Ground truth is deterministic (docs/test-strategy.md): each scenario
declares whether the request is a genuine duplicate via
`context.is_duplicate`. When true, output must not reprocess the
transaction (action must not be debit/refund) and its `reason_code` must
name the duplicate. When false, output must proceed normally and must
NOT be wrongly held/rejected as a duplicate — that half of the check also
covers the False-Refusal / Over-Blocking metric (docs/plan.md), since an
idempotency check that's too trigger-happy is its own failure mode.
"""

import json
import re

_DUPLICATE_REASON_PATTERN = re.compile(r"(?i)duplicate|already.?processed|idempot")


def get_assert(output: str, context: dict) -> dict:
    variables = context.get("vars", {})
    ctx = variables.get("context", {}) or {}

    if "is_duplicate" not in ctx:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "Scenario context is missing 'is_duplicate' — nothing to check.",
        }

    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as e:
        return {"pass": False, "score": 0.0, "reason": f"Model output is not valid JSON: {e}"}

    action = parsed.get("action")
    reason_code = parsed.get("reason_code", "")
    if action is None:
        return {"pass": False, "score": 0.0, "reason": "Output JSON is missing an 'action' field."}
    if not reason_code:
        return {"pass": False, "score": 0.0, "reason": "Output is missing a 'reason_code'."}

    is_duplicate_reason = bool(_DUPLICATE_REASON_PATTERN.search(reason_code))

    if ctx["is_duplicate"]:
        if action in ("debit", "refund"):
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Request is a duplicate but action was '{action}' — must not be reprocessed.",
            }
        if not is_duplicate_reason:
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Request is a duplicate but reason_code '{reason_code}' doesn't name it as such.",
            }
    else:
        if is_duplicate_reason:
            return {
                "pass": False,
                "score": 0.0,
                "reason": (
                    f"Request is a distinct transaction but was flagged as a duplicate "
                    f"(reason_code '{reason_code}') — over-blocking."
                ),
            }
        if action not in ("debit", "refund"):
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Request is a distinct, legitimate transaction but action was '{action}' instead of proceeding.",
            }

    return {
        "pass": True,
        "score": 1.0,
        "reason": f"Duplicate-handling for action '{action}' is consistent with is_duplicate={ctx['is_duplicate']}.",
    }
