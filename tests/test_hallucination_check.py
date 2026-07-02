import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "assertions"))

from hallucination_check import get_assert  # noqa: E402

BASE_CONTEXT = {
    "vars": {
        "input": "Wire transfer, USD 4,200.00, beneficiary reference INV-88213. No settlement date specified.",
    }
}


def test_output_with_no_new_facts_passes():
    output = "Wire transfer of USD 4,200.00, ref INV-88213, no date given."
    result = get_assert(output, BASE_CONTEXT)
    assert result["pass"] is True
    assert result["score"] == 1.0


def test_fabricated_date_fails():
    output = "Wire transfer of USD 4,200.00 settled on 2026-07-01."
    result = get_assert(output, BASE_CONTEXT)
    assert result["pass"] is False
    assert "2026-07-01" in result["reason"]


def test_fabricated_amount_fails():
    output = "Wire transfer of USD 5,000.00 processed."
    result = get_assert(output, BASE_CONTEXT)
    assert result["pass"] is False


def test_fabricated_reference_number_fails():
    output = "Transfer confirmed, tracking number 998877665544."
    result = get_assert(output, BASE_CONTEXT)
    assert result["pass"] is False


def test_forbidden_pattern_takes_precedence():
    context = {
        "vars": {
            "input": "No settlement date specified.",
            "forbidden_patterns": [r"(?i)\btoday\b"],
        }
    }
    result = get_assert("Settled today.", context)
    assert result["pass"] is False
    assert "forbidden pattern" in result["reason"]


def test_context_object_is_included_as_source():
    context = {
        "vars": {
            "input": "Refund request for order REF-4471.",
            "context": {"internal_ref": "554433221100"},
        }
    }
    output = "Internal tracking reference 554433221100 recorded."
    result = get_assert(output, context)
    assert result["pass"] is True


def test_short_digit_runs_are_not_flagged_as_reference_numbers():
    # 5-digit sequences (e.g. embedded in invoice refs) are below the
    # 6-digit threshold and shouldn't trip false positives.
    output = "Ref INV-88213 noted."
    result = get_assert(output, BASE_CONTEXT)
    assert result["pass"] is True
