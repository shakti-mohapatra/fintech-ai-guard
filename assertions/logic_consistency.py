"""promptfoo custom assertion: grades business-logic consistency of a
structured transaction-action decision (debit/refund/hold/reject).

Contract (promptfoo `type: python`): get_assert(output, context) -> dict.
Ground truth is deterministic (docs/test-strategy.md): each scenario
declares the outcome that is/isn't acceptable via `context.forbidden_actions`
and/or `context.expected_action`, checked against the parsed `action` field
of the model's JSON output (see scenarios/schema/transaction_action.schema.json).
`forbidden_patterns` remains a secondary, text-level backstop for traps the
structured check can't reach.
"""

import json
import re


def get_assert(output: str, context: dict) -> dict:
    variables = context.get("vars", {})
    ctx = variables.get("context", {}) or {}
    forbidden_patterns = variables.get("forbidden_patterns", [])

    for pattern in forbidden_patterns:
        if re.search(pattern, output):
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Output matches forbidden pattern '{pattern}'.",
            }

    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as e:
        return {"pass": False, "score": 0.0, "reason": f"Model output is not valid JSON: {e}"}

    action = parsed.get("action")
    if action is None:
        return {"pass": False, "score": 0.0, "reason": "Output JSON is missing an 'action' field."}

    forbidden_actions = ctx.get("forbidden_actions", [])
    if action in forbidden_actions:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Action '{action}' is forbidden for this scenario (forbidden_actions={forbidden_actions}).",
        }

    expected_action = ctx.get("expected_action")
    if expected_action is not None and action != expected_action:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Expected action '{expected_action}', got '{action}'.",
        }

    if not parsed.get("reason_code"):
        return {
            "pass": False,
            "score": 0.0,
            "reason": "Output is missing a 'reason_code' — every non-trivial action must be explainable.",
        }

    return {
        "pass": True,
        "score": 1.0,
        "reason": f"Action '{action}' is consistent with scenario business rules.",
    }
