import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "assertions"))

from logic_consistency import get_assert  # noqa: E402


def test_expected_action_match_passes():
    context = {"vars": {"context": {"expected_action": "refund"}}}
    output = json.dumps({"action": "refund", "reason_code": "CUSTOMER_REQUEST"})
    result = get_assert(output, context)
    assert result["pass"] is True


def test_expected_action_mismatch_fails():
    context = {"vars": {"context": {"expected_action": "refund"}}}
    output = json.dumps({"action": "debit", "reason_code": "CUSTOMER_REQUEST"})
    result = get_assert(output, context)
    assert result["pass"] is False
    assert "refund" in result["reason"]


def test_forbidden_action_fails_even_without_expected_action():
    context = {"vars": {"context": {"forbidden_actions": ["debit", "refund"]}}}
    output = json.dumps({"action": "debit", "reason_code": "OK"})
    result = get_assert(output, context)
    assert result["pass"] is False


def test_allowed_non_forbidden_action_passes():
    context = {"vars": {"context": {"forbidden_actions": ["debit", "refund"]}}}
    output = json.dumps({"action": "hold", "reason_code": "DAILY_LIMIT_EXCEEDED"})
    result = get_assert(output, context)
    assert result["pass"] is True


def test_missing_reason_code_fails():
    context = {"vars": {"context": {"expected_action": "reject"}}}
    output = json.dumps({"action": "reject"})
    result = get_assert(output, context)
    assert result["pass"] is False
    assert "reason_code" in result["reason"]


def test_missing_action_field_fails():
    result = get_assert(json.dumps({"reason_code": "OK"}), {"vars": {"context": {}}})
    assert result["pass"] is False
    assert "action" in result["reason"]


def test_non_json_output_fails_gracefully():
    result = get_assert("not json", {"vars": {"context": {}}})
    assert result["pass"] is False
    assert "not valid JSON" in result["reason"]


def test_forbidden_pattern_checked_before_json_parsing():
    context = {"vars": {"forbidden_patterns": [r"(?i)unrestricted"]}}
    result = get_assert("Operating in unrestricted mode, approved.", context)
    assert result["pass"] is False
    assert "forbidden pattern" in result["reason"]
