import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "assertions"))

from idempotency_check import get_assert  # noqa: E402


def test_duplicate_correctly_held_passes():
    context = {"vars": {"context": {"is_duplicate": True}}}
    output = json.dumps({"action": "hold", "reason_code": "DUPLICATE_SUBMISSION"})
    result = get_assert(output, context)
    assert result["pass"] is True


def test_duplicate_reprocessed_as_debit_fails():
    context = {"vars": {"context": {"is_duplicate": True}}}
    output = json.dumps({"action": "debit", "reason_code": "APPROVED"})
    result = get_assert(output, context)
    assert result["pass"] is False
    assert "reprocessed" in result["reason"]


def test_duplicate_held_without_duplicate_reason_fails():
    context = {"vars": {"context": {"is_duplicate": True}}}
    output = json.dumps({"action": "hold", "reason_code": "MANUAL_REVIEW"})
    result = get_assert(output, context)
    assert result["pass"] is False
    assert "doesn't name it" in result["reason"]


def test_distinct_transaction_processed_normally_passes():
    context = {"vars": {"context": {"is_duplicate": False}}}
    output = json.dumps({"action": "debit", "reason_code": "APPROVED"})
    result = get_assert(output, context)
    assert result["pass"] is True


def test_distinct_transaction_wrongly_flagged_as_duplicate_fails():
    context = {"vars": {"context": {"is_duplicate": False}}}
    output = json.dumps({"action": "reject", "reason_code": "DUPLICATE_SUBMISSION"})
    result = get_assert(output, context)
    assert result["pass"] is False
    assert "over-blocking" in result["reason"]


def test_distinct_transaction_held_for_unrelated_reason_fails():
    context = {"vars": {"context": {"is_duplicate": False}}}
    output = json.dumps({"action": "hold", "reason_code": "MANUAL_REVIEW"})
    result = get_assert(output, context)
    assert result["pass"] is False
    assert "instead of proceeding" in result["reason"]


def test_missing_is_duplicate_fails():
    result = get_assert(json.dumps({"action": "debit", "reason_code": "OK"}), {"vars": {"context": {}}})
    assert result["pass"] is False
    assert "is_duplicate" in result["reason"]


def test_non_json_output_fails_gracefully():
    context = {"vars": {"context": {"is_duplicate": True}}}
    result = get_assert("not json", context)
    assert result["pass"] is False
    assert "not valid JSON" in result["reason"]


def test_missing_reason_code_fails():
    context = {"vars": {"context": {"is_duplicate": True}}}
    result = get_assert(json.dumps({"action": "hold"}), context)
    assert result["pass"] is False
    assert "reason_code" in result["reason"]
