import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "assertions"))

from numeric_precision import get_assert  # noqa: E402


def test_expected_total_match_passes():
    context = {"vars": {"context": {"total_field": "total_amount", "expected_total": 541.75}}}
    output = json.dumps({"converted_amount_usd": 1.0, "total_amount": 541.75})
    result = get_assert(output, context)
    assert result["pass"] is True


def test_expected_total_mismatch_fails():
    context = {"vars": {"context": {"total_field": "total_amount", "expected_total": 541.75}}}
    output = json.dumps({"total_amount": 500.00})
    result = get_assert(output, context)
    assert result["pass"] is False
    assert "500.0" in result["reason"]


def test_expected_total_within_epsilon_passes():
    context = {"vars": {"context": {"total_field": "total_amount", "expected_total": 189.54}}}
    output = json.dumps({"total_amount": 189.545})
    result = get_assert(output, context)
    assert result["pass"] is True


def test_component_sum_consistency_passes():
    context = {
        "vars": {
            "context": {
                "components": ["subtotal", "tax_amount"],
                "total_field": "total_amount",
                "expected_total": 189.54,
            }
        }
    }
    output = json.dumps({"subtotal": 175.50, "tax_amount": 14.04, "total_amount": 189.54})
    result = get_assert(output, context)
    assert result["pass"] is True


def test_component_sum_inconsistency_fails():
    context = {
        "vars": {
            "context": {
                "components": ["subtotal", "tax_amount"],
                "total_field": "total_amount",
            }
        }
    }
    output = json.dumps({"subtotal": 175.50, "tax_amount": 14.04, "total_amount": 190.00})
    result = get_assert(output, context)
    assert result["pass"] is False


def test_rounding_boundary_fails_when_wrong_direction_chosen():
    context = {"vars": {"context": {"total_field": "total_amount", "expected_total": 10.01}}}
    output = json.dumps({"total_amount": 10.00})
    result = get_assert(output, context)
    assert result["pass"] is False


def test_missing_total_field_fails():
    context = {"vars": {"context": {"total_field": "total_amount", "expected_total": 10.01}}}
    result = get_assert(json.dumps({}), context)
    assert result["pass"] is False
    assert "missing or not numeric" in result["reason"]


def test_non_json_output_fails_gracefully():
    context = {"vars": {"context": {"total_field": "total_amount", "expected_total": 10.01}}}
    result = get_assert("not json", context)
    assert result["pass"] is False
    assert "not valid JSON" in result["reason"]


def test_scenario_with_no_check_inputs_fails():
    result = get_assert(json.dumps({"total_amount": 10.0}), {"vars": {}})
    assert result["pass"] is False
    assert "nothing to check" in result["reason"]


def test_missing_component_field_fails():
    context = {"vars": {"context": {"components": ["subtotal", "tax_amount"], "total_field": "total_amount"}}}
    output = json.dumps({"subtotal": 175.50, "total_amount": 189.54})
    result = get_assert(output, context)
    assert result["pass"] is False
    assert "tax_amount" in result["reason"]
