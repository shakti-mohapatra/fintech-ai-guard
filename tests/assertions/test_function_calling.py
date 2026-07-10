import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "assertions"))

from function_calling import get_assert  # noqa: E402


def _context(expected_tools, trace_names, **extra_vars):
    trace = [{"name": name, "args": {}, "result": "{}"} for name in trace_names]
    vars_ = {"expected_tools": expected_tools, **extra_vars}
    return {
        "vars": vars_,
        "metadata": {"tool_calls": trace, "ledger_after": {}},
    }


def test_no_metadata_fails():
    result = get_assert("some output", {"vars": {"expected_tools": ["balance_tool"]}})
    assert result["pass"] is False
    assert "tool_calls metadata" in result["reason"]


def test_exact_sequence_match_passes():
    context = _context(["balance_tool", "transfer_tool"], ["balance_tool", "transfer_tool"], tool_order_matters=True)
    result = get_assert("done", context)
    assert result["pass"] is True


def test_sequence_mismatch_fails():
    context = _context(["balance_tool", "transfer_tool"], ["transfer_tool", "balance_tool"], tool_order_matters=True)
    result = get_assert("done", context)
    assert result["pass"] is False
    assert "sequence" in result["reason"]


def test_multiset_ignores_order_by_default():
    context = _context(["balance_tool", "transfer_tool"], ["transfer_tool", "balance_tool"])
    result = get_assert("done", context)
    assert result["pass"] is True


def test_double_execution_fails_multiset_count():
    context = _context(["transfer_tool"], ["transfer_tool", "transfer_tool"])
    result = get_assert("done", context)
    assert result["pass"] is False


def test_unexpected_extra_tool_call_fails():
    context = _context(["balance_tool"], ["balance_tool", "transfer_tool"])
    result = get_assert("done", context)
    assert result["pass"] is False


def test_ledger_check_passes_on_matching_balance():
    context = _context(["transfer_tool"], ["transfer_tool"])
    context["vars"]["ledger_checks"] = [{"account_id": "ACC-1001", "expected_balance_minor": 95000}]
    context["metadata"]["ledger_after"] = {"ACC-1001": 95000}
    result = get_assert("done", context)
    assert result["pass"] is True


def test_ledger_check_fails_on_mismatched_balance():
    context = _context(["transfer_tool"], ["transfer_tool"])
    context["vars"]["ledger_checks"] = [{"account_id": "ACC-1001", "expected_balance_minor": 95000}]
    context["metadata"]["ledger_after"] = {"ACC-1001": 90000}
    result = get_assert("done", context)
    assert result["pass"] is False
    assert "ACC-1001" in result["reason"]


def test_forbidden_pattern_match_fails():
    context = _context(["transfer_tool"], ["transfer_tool"])
    context["vars"]["forbidden_patterns"] = [r"(?i)successfully"]
    result = get_assert("Your transfer was successfully completed.", context)
    assert result["pass"] is False


def test_required_pattern_missing_fails():
    context = _context(["transfer_tool"], ["transfer_tool"])
    context["vars"]["required_patterns"] = [r"925(\.00)?\b"]
    result = get_assert("Your new balance is $999.00.", context)
    assert result["pass"] is False
    assert "925" in result["reason"]


def test_required_pattern_present_passes():
    context = _context(["transfer_tool"], ["transfer_tool"])
    context["vars"]["required_patterns"] = [r"925(\.00)?\b"]
    result = get_assert("Your new balance is $925.00.", context)
    assert result["pass"] is True


def test_all_checks_combined_pass():
    context = _context(["balance_tool", "transfer_tool"], ["balance_tool", "transfer_tool"], tool_order_matters=True)
    context["vars"]["ledger_checks"] = [{"account_id": "ACC-1001", "expected_balance_minor": 90000}]
    context["vars"]["forbidden_patterns"] = [r"(?i)failed"]
    context["vars"]["required_patterns"] = [r"900(\.00)?\b"]
    context["metadata"]["ledger_after"] = {"ACC-1001": 90000}
    result = get_assert("Transferred. Your new balance is $900.00.", context)
    assert result["pass"] is True
