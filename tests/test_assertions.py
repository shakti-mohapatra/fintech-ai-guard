import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "assertions"))

from schema_validator import get_assert  # noqa: E402

SCHEMA_VAR = {"vars": {"schema_file": "scenarios/schema/transfer_request.schema.json"}}


def test_valid_transfer_passes():
    output = json.dumps({"amount": 100.0, "currency": "USD", "recipient_account": "1234567890"})
    result = get_assert(output, SCHEMA_VAR)
    assert result["pass"] is True
    assert result["score"] == 1.0


def test_missing_required_field_fails():
    output = json.dumps({"amount": 100.0, "currency": "USD"})
    result = get_assert(output, SCHEMA_VAR)
    assert result["pass"] is False
    assert "recipient_account" in result["reason"]


def test_wrong_type_fails():
    output = json.dumps({"amount": "not-a-number", "currency": "USD", "recipient_account": "1234567890"})
    result = get_assert(output, SCHEMA_VAR)
    assert result["pass"] is False


def test_non_json_output_fails_gracefully():
    result = get_assert("this is not json", SCHEMA_VAR)
    assert result["pass"] is False
    assert "not valid JSON" in result["reason"]


def test_missing_schema_file_var_fails_gracefully():
    result = get_assert("{}", {"vars": {}})
    assert result["pass"] is False
    assert "schema_file" in result["reason"]


def test_nonexistent_schema_path_fails_gracefully():
    result = get_assert("{}", {"vars": {"schema_file": "scenarios/schema/does_not_exist.schema.json"}})
    assert result["pass"] is False
    assert "not found" in result["reason"]
