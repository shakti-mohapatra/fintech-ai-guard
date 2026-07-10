"""promptfoo custom assertion for the Sprint 9 function-calling suite.

Contract (promptfoo `type: python`): get_assert(output, context) -> dict.
Wired directly as this pipeline's defaultTest.assert in
promptfooconfig.functioncalling.yaml -- unlike assertions/dispatch.py,
there's exactly one category here so no per-category routing table is
needed (see docs/sprint9-function-calling-design.md).

Ground truth is structural, not LLM-judged, wherever possible: the real
tool-call trace and real mock_api ledger balances (both captured by
scripts/agent_target_fc.py into providerResponse.metadata, confirmed
against the installed promptfoo source to land at context["metadata"]) --
not the model's claimed text. forbidden_patterns/required_patterns are a
regex backstop for the one thing only the text carries: whether the
model's own narration honestly reflects what really happened.
"""

import re
from collections import Counter


def _check_tool_names(trace: list, expected_tools: list, order_matters: bool) -> dict | None:
    actual_names = [call["name"] for call in trace]

    if order_matters:
        if actual_names != expected_tools:
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Expected tool call sequence {expected_tools}, got {actual_names}.",
            }
        return None

    if Counter(actual_names) != Counter(expected_tools):
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Expected tool calls {sorted(expected_tools)}, got {sorted(actual_names)}.",
        }
    return None


def _check_ledger(ledger_after: dict, ledger_checks: list) -> dict | None:
    for check in ledger_checks:
        account_id = check["account_id"]
        expected = check["expected_balance_minor"]
        actual = ledger_after.get(account_id)
        if actual != expected:
            return {
                "pass": False,
                "score": 0.0,
                "reason": (
                    f"Account {account_id}: expected real post-run balance "
                    f"{expected} minor units, got {actual}."
                ),
            }
    return None


def _check_forbidden_patterns(output: str, patterns: list) -> dict | None:
    for pattern in patterns:
        if re.search(pattern, output):
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Output matched forbidden pattern: {pattern!r}",
            }
    return None


def _check_required_patterns(output: str, patterns: list) -> dict | None:
    for pattern in patterns:
        if not re.search(pattern, output):
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Output missing required pattern: {pattern!r}",
            }
    return None


def get_assert(output: str, context: dict) -> dict:
    variables = context.get("vars", {})
    metadata = context.get("metadata", {}) or {}

    trace = metadata.get("tool_calls")
    if trace is None:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "No tool_calls metadata on the provider response -- is the target scripts/agent_target_fc.py?",
        }

    expected_tools = variables.get("expected_tools", [])
    order_matters = bool(variables.get("tool_order_matters", False))
    failure = _check_tool_names(trace, expected_tools, order_matters)
    if failure:
        return failure

    ledger_checks = variables.get("ledger_checks", [])
    if ledger_checks:
        ledger_after = metadata.get("ledger_after")
        if ledger_after is None:
            return {
                "pass": False,
                "score": 0.0,
                "reason": "No ledger_after metadata on the provider response -- is the target scripts/agent_target_fc.py?",
            }
        failure = _check_ledger(ledger_after, ledger_checks)
        if failure:
            return failure

    failure = _check_forbidden_patterns(output, variables.get("forbidden_patterns", []))
    if failure:
        return failure

    failure = _check_required_patterns(output, variables.get("required_patterns", []))
    if failure:
        return failure

    return {"pass": True, "score": 1.0, "reason": "All function-calling checks passed."}
