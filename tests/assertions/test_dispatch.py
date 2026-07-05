import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "assertions"))

import tone_rubric  # noqa: E402
from dispatch import get_assert  # noqa: E402


def _ctx(category, **vars_extra):
    return {"vars": {"category": category, **vars_extra}}


def test_hallucination_routes_to_hallucination_check():
    context = _ctx("hallucination", input="Wire transfer, USD 4,200.00, ref INV-88213.")
    result = get_assert("Wire transfer of USD 4,200.00, ref INV-88213.", context)
    assert result["pass"] is True


def test_injection_routes_to_injection_resistance():
    context = _ctx("injection", forbidden_patterns=[r"(?i)\bapproved\b"])
    result = get_assert("Transfer approved.", context)
    assert result["pass"] is False


def test_schema_compliance_routes_to_schema_validator():
    # Mirrors the real scenario file shape: schema_file nested under
    # vars.context, not flat under vars (see scenarios/scenario.schema.json).
    context = {
        "vars": {
            "category": "schema-compliance",
            "context": {"schema_file": "scenarios/schema/transfer_request.schema.json"},
        }
    }
    output = json.dumps({"amount": 100.0, "currency": "USD", "recipient_account": "1234567890"})
    result = get_assert(output, context)
    assert result["pass"] is True


def test_numeric_precision_routes_correctly():
    context = {"vars": {"category": "numeric-precision", "context": {"total_field": "total_amount", "expected_total": 10.01}}}
    result = get_assert(json.dumps({"total_amount": 10.01}), context)
    assert result["pass"] is True


def test_logic_consistency_routes_correctly():
    context = {"vars": {"category": "logic-consistency", "context": {"expected_action": "refund"}}}
    result = get_assert(json.dumps({"action": "refund", "reason_code": "CUSTOMER_REQUEST"}), context)
    assert result["pass"] is True


def test_idempotency_routes_correctly():
    context = {"vars": {"category": "idempotency", "context": {"is_duplicate": True}}}
    result = get_assert(json.dumps({"action": "hold", "reason_code": "DUPLICATE_SUBMISSION"}), context)
    assert result["pass"] is True


def test_pii_pci_routes_correctly():
    context = {"vars": {"category": "pii-pci"}}
    result = get_assert("Your card 424242******4242 was charged.", context)
    assert result["pass"] is True


def test_unknown_category_fails_gracefully():
    context = _ctx("not-a-real-category")
    result = get_assert("anything", context)
    assert result["pass"] is False
    assert "No assertion wired" in result["reason"]


def test_tone_disclosure_routes_to_tone_rubric(monkeypatch):
    # Mocked grader — no real HTTP call, no quota spent, per PROGRESS.md's
    # unit-test-only decision for this session.
    monkeypatch.setattr(
        tone_rubric, "_call_grader", lambda prompt, model: json.dumps({"pass": True, "reason": "ok"})
    )
    context = _ctx("tone-disclosure", expected_behavior="Must include a disclaimer.")
    result = get_assert("Not financial advice; consult an advisor.", context)
    assert result["pass"] is True


# --- l3-data-extraction: layered schema + numeric check --------------------

def _l3_context(**extra_ctx):
    ctx = {"schema_file": "scenarios/schema/l3_line_item.schema.json", **extra_ctx}
    return {"vars": {"category": "l3-data-extraction", "context": ctx}}


def _valid_l3_output(total_amount=484.40):
    return json.dumps(
        {
            "po_number": "PO-55217",
            "line_items": [
                {"description": "USB-C Cable", "quantity": 50, "unit_cost": 2.50, "commodity_code": "26121600"}
            ],
            "freight_amount": 35.0,
            "tax_amount": 32.4,
            "total_amount": total_amount,
        }
    )


def test_l3_passes_schema_and_numeric_check():
    context = _l3_context(total_field="total_amount", expected_total=484.40)
    result = get_assert(_valid_l3_output(484.40), context)
    assert result["pass"] is True


def test_l3_fails_schema_before_numeric_check_runs():
    context = _l3_context(total_field="total_amount", expected_total=484.40)
    # Missing required 'po_number' -> schema_validator fails first.
    bad_output = json.dumps({"line_items": [], "tax_amount": 0, "total_amount": 484.40})
    result = get_assert(bad_output, context)
    assert result["pass"] is False


def test_l3_passes_schema_but_fails_numeric_reconciliation():
    context = _l3_context(total_field="total_amount", expected_total=484.40)
    result = get_assert(_valid_l3_output(999.99), context)
    assert result["pass"] is False


def test_l3_skips_numeric_check_when_no_numeric_context_given():
    # No expected_total/components in context -> only the schema check runs.
    context = _l3_context()
    result = get_assert(_valid_l3_output(999.99), context)
    assert result["pass"] is True


def test_real_schema_compliance_scenario_file_round_trips():
    # Regression guard for the schema_file nesting bug caught during Sprint 4
    # wiring: schema_validator.py originally read vars.schema_file (flat),
    # but every real scenario file nests it under vars.context.schema_file.
    import yaml

    path = (
        Path(__file__).resolve().parent.parent.parent
        / "scenarios"
        / "schema-compliance"
        / "schema-compliance-transfer-basic-001.yaml"
    )
    scenario = yaml.safe_load(path.read_text(encoding="utf-8"))
    output = json.dumps({"amount": 250.00, "currency": "USD", "recipient_account": "9988776655", "memo": "consulting fee"})
    result = get_assert(output, {"vars": scenario["vars"]})
    assert result["pass"] is True, result["reason"]
