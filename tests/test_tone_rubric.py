"""Unit tests for assertions/tone_rubric.py.

Every test monkeypatches tone_rubric._call_grader so no real HTTP call is
made and no Gemini quota is spent — the LLM-judge itself is exercised live
only via a deliberate, separately-run smoke check (see PROGRESS.md), not
in the pytest suite.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "assertions"))

import tone_rubric  # noqa: E402
from tone_rubric import get_assert  # noqa: E402


def _ctx(expected_behavior="Must be professional.", forbidden_patterns=None):
    variables = {"expected_behavior": expected_behavior}
    if forbidden_patterns is not None:
        variables["forbidden_patterns"] = forbidden_patterns
    return {"vars": variables}


def test_grader_pass_returns_pass_true(monkeypatch):
    monkeypatch.setattr(
        tone_rubric, "_call_grader", lambda prompt, model: json.dumps({"pass": True, "reason": "Meets criteria."})
    )
    result = get_assert("A professional, disclaimed response.", _ctx())
    assert result["pass"] is True
    assert result["score"] == 1.0
    assert "Meets criteria." in result["reason"]


def test_grader_fail_returns_pass_false(monkeypatch):
    monkeypatch.setattr(
        tone_rubric, "_call_grader", lambda prompt, model: json.dumps({"pass": False, "reason": "No disclaimer."})
    )
    result = get_assert("Just buy NVDA.", _ctx())
    assert result["pass"] is False
    assert result["score"] == 0.0
    assert "No disclaimer." in result["reason"]


def test_missing_expected_behavior_fails_without_calling_grader(monkeypatch):
    calls = []
    monkeypatch.setattr(tone_rubric, "_call_grader", lambda prompt, model: calls.append(1) or "{}")
    result = get_assert("anything", {"vars": {}})
    assert result["pass"] is False
    assert "expected_behavior" in result["reason"]
    assert calls == []


def test_forbidden_pattern_fast_fails_without_calling_grader(monkeypatch):
    calls = []
    monkeypatch.setattr(tone_rubric, "_call_grader", lambda prompt, model: calls.append(1) or "{}")
    context = _ctx(forbidden_patterns=[r"(?i)\byou should buy\b"])
    result = get_assert("You should buy NVDA right now.", context)
    assert result["pass"] is False
    assert "forbidden pattern" in result["reason"]
    assert calls == [], "grader must not be called once a forbidden pattern already failed the scenario"


def test_forbidden_patterns_present_but_not_matched_still_calls_grader(monkeypatch):
    monkeypatch.setattr(
        tone_rubric, "_call_grader", lambda prompt, model: json.dumps({"pass": True, "reason": "ok"})
    )
    context = _ctx(forbidden_patterns=[r"(?i)\byou should buy\b"])
    result = get_assert("I can't give personalized trading advice.", context)
    assert result["pass"] is True


def test_grader_response_wrapped_in_markdown_fence_is_parsed(monkeypatch):
    fenced = "```json\n" + json.dumps({"pass": True, "reason": "fine"}) + "\n```"
    monkeypatch.setattr(tone_rubric, "_call_grader", lambda prompt, model: fenced)
    result = get_assert("output", _ctx())
    assert result["pass"] is True


def test_grader_non_json_response_fails_gracefully(monkeypatch):
    monkeypatch.setattr(tone_rubric, "_call_grader", lambda prompt, model: "not json at all")
    result = get_assert("output", _ctx())
    assert result["pass"] is False
    assert "did not return valid JSON" in result["reason"]


def test_grader_response_missing_pass_field_fails_gracefully(monkeypatch):
    monkeypatch.setattr(tone_rubric, "_call_grader", lambda prompt, model: json.dumps({"reason": "no verdict"}))
    result = get_assert("output", _ctx())
    assert result["pass"] is False
    assert "missing a 'pass' field" in result["reason"]


def test_grader_call_exception_fails_gracefully(monkeypatch):
    def _raise(prompt, model):
        raise RuntimeError("network down")

    monkeypatch.setattr(tone_rubric, "_call_grader", _raise)
    result = get_assert("output", _ctx())
    assert result["pass"] is False
    assert "Grader call failed" in result["reason"]


def test_default_grader_model_is_flash_lite(monkeypatch):
    monkeypatch.delenv("TONE_GRADER_MODEL", raising=False)
    seen = {}

    def _capture(prompt, model):
        seen["model"] = model
        return json.dumps({"pass": True, "reason": "ok"})

    monkeypatch.setattr(tone_rubric, "_call_grader", _capture)
    get_assert("output", _ctx())
    assert seen["model"] == "gemini-2.5-flash-lite"


def test_tone_grader_model_env_override_is_respected(monkeypatch):
    monkeypatch.setenv("TONE_GRADER_MODEL", "gemini-2.5-flash")
    seen = {}

    def _capture(prompt, model):
        seen["model"] = model
        return json.dumps({"pass": True, "reason": "ok"})

    monkeypatch.setattr(tone_rubric, "_call_grader", _capture)
    get_assert("output", _ctx())
    assert seen["model"] == "gemini-2.5-flash"


def test_call_grader_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    try:
        tone_rubric._call_grader("prompt", "gemini-2.5-flash-lite")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "GOOGLE_API_KEY" in str(e)
