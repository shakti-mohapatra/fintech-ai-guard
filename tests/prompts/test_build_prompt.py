"""Unit tests for prompts/build_prompt.js — the category-conditional prompt
builder that embeds the real JSON Schema for structured-output categories
(see that file's own header comment for the Sprint 4 rationale: without an
embedded schema, models invent plausible-but-wrong field names).

This file had zero dedicated coverage before Sprint 12 — it was only
exercised transitively through a real (costly) `promptfoo eval` run. These
tests invoke the actual build_prompt.js via a small Node subprocess bridge
(_run_build_prompt.js) so the real file is under test, not a Python
reimplementation of its logic — and cost nothing (no network, no API key).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE = Path(__file__).resolve().parent / "_run_build_prompt.js"


def _run(vars_: dict) -> str:
    result = subprocess.run(
        ["node", str(BRIDGE), json.dumps(vars_)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"build_prompt.js failed (exit {result.returncode}): {result.stderr}")
    return result.stdout


def _run_expect_failure(vars_: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(BRIDGE), json.dumps(vars_)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_non_json_category_gets_synthetic_disclaimer_and_raw_input():
    output = _run({"category": "hallucination", "input": "Summarize: test memo text."})
    assert "synthetic test suite" in output
    assert "fabricated test data" in output
    assert "Summarize: test memo text." in output
    # Must NOT get the JSON-only instruction meant for structured categories.
    assert "Respond with ONLY a single valid JSON object" not in output


def test_json_category_without_schema_file_gets_generic_json_instruction():
    output = _run({"category": "logic-consistency", "input": "Decide the action.", "context": {}})
    assert "Respond with ONLY a single valid JSON object" in output
    assert "matching exactly this JSON Schema" not in output
    assert "Decide the action." in output


def test_json_category_with_schema_file_embeds_real_schema_verbatim():
    output = _run(
        {
            "category": "schema-compliance",
            "input": "Transfer 10.00 USD to account 1234567890.",
            "context": {"schema_file": "scenarios/schema/transfer_request.schema.json"},
        }
    )
    assert "matching exactly this JSON Schema" in output
    # Proves the real schema file was read off disk, not a hardcoded stub —
    # this is a field name that only exists in transfer_request.schema.json.
    assert "recipient_account" in output
    assert "no extra fields" in output
    assert "Transfer 10.00 USD to account 1234567890." in output


def test_json_category_schema_choice_is_per_scenario_not_hardcoded():
    # A second, structurally different schema (transaction_action) must
    # produce different embedded content — proves the schema_file var
    # actually drives which schema gets embedded, not a single fixed one.
    output = _run(
        {
            "category": "logic-consistency",
            "input": "Decide the action.",
            "context": {"schema_file": "scenarios/schema/transaction_action.schema.json"},
        }
    )
    assert "reason_code" in output
    assert "recipient_account" not in output


def test_all_five_json_categories_get_json_instruction():
    # Must match assertions/dispatch.py's JSON-output category set exactly —
    # this list drifting out of sync with dispatch.py would silently send a
    # free-text prompt for a category graded as structured JSON.
    json_categories = [
        "schema-compliance",
        "numeric-precision",
        "logic-consistency",
        "idempotency",
        "l3-data-extraction",
    ]
    for category in json_categories:
        output = _run({"category": category, "input": "test input", "context": {}})
        assert "Respond with ONLY a single valid JSON object" in output, category


def test_missing_schema_file_fails_loudly_not_silently():
    # A typo'd or missing schema_file must surface as a real failure (Node
    # process exits non-zero with an fs error), not silently fall back to
    # the no-schema generic instruction — a silent fallback here would mask
    # a scenario-authoring mistake as a passing test run.
    result = _run_expect_failure(
        {
            "category": "schema-compliance",
            "input": "test",
            "context": {"schema_file": "scenarios/schema/does_not_exist.schema.json"},
        }
    )
    assert result.returncode != 0
    assert "ENOENT" in result.stderr or "no such file" in result.stderr.lower()
