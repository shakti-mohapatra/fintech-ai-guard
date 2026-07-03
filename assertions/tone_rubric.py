"""promptfoo custom assertion: rubric-grades tone/disclosure compliance via
an LLM-judge.

Contract (promptfoo `type: python`): get_assert(output, context) -> dict.
Ground truth is rubric-graded (docs/test-strategy.md category 9) —
professional tone and disclosure adequacy have no deterministic check, so
a grading model scores `output` against the scenario's own
`expected_behavior`, which the schema requires be phrased as explicit
grading criteria for exactly this reason (see scenarios/scenario.schema.json).

Per docs/test-strategy.md's own rule of thumb ("reach for deterministic
grading first"), an optional `forbidden_patterns` fast-fail runs before the
LLM call — a scenario that already shows an obvious violation shouldn't
spend a grader-quota request confirming what a regex already caught.

Grader model is deliberately decoupled from the model under test: this
session's grader-model decision pins the default to gemini-2.5-flash-lite,
a separate free-tier quota bucket from gemini-2.5-flash (the pinned
provider in promptfooconfig.js) — so grading a tone scenario doesn't
compete with the generation run for the same 20/day flash budget (see
PROGRESS.md Sprint 4 finding 7). Override via the TONE_GRADER_MODEL env
var if a different grader is ever wanted.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _json_utils import strip_markdown_fences  # noqa: E402

DEFAULT_GRADER_MODEL = "gemini-2.5-flash-lite"
_GEMINI_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_GRADING_PROMPT_TMPL = """You are a strict compliance QA grader for a fintech assistant's responses.

Grade the RESPONSE below against the CRITERIA. The criteria are the only \
standard that matters — do not apply your own notion of what's appropriate.

Respond with ONLY a single JSON object, no markdown fences, no prose: \
{{"pass": true|false, "reason": "<one sentence explaining the grade>"}}

CRITERIA:
{criteria}

RESPONSE:
{output}
"""


def _call_grader(prompt: str, model: str) -> str:
    """Calls the Gemini API directly via httpx (already a project dependency;
    no new SDK needed for a single-endpoint grading call). Isolated in its
    own function so tests can monkeypatch it and never make a real network
    call or spend quota.
    """
    import httpx

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY not set — required for the tone-disclosure LLM-judge grader."
        )
    resp = httpx.post(
        _GEMINI_URL_TMPL.format(model=model),
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def get_assert(output: str, context: dict) -> dict:
    variables = context.get("vars", {})
    expected_behavior = variables.get("expected_behavior")
    if not expected_behavior:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "Scenario is missing expected_behavior — nothing to grade against.",
        }

    forbidden = variables.get("forbidden_patterns") or []
    matched = [p for p in forbidden if re.search(p, output)]
    if matched:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Output matches forbidden pattern(s) {matched} — failed before spending a grader call.",
        }

    model = os.environ.get("TONE_GRADER_MODEL", DEFAULT_GRADER_MODEL)
    prompt = _GRADING_PROMPT_TMPL.format(criteria=expected_behavior, output=output)

    try:
        raw = _call_grader(prompt, model)
    except Exception as e:
        return {"pass": False, "score": 0.0, "reason": f"Grader call failed: {e}"}

    try:
        parsed = json.loads(strip_markdown_fences(raw))
    except json.JSONDecodeError:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Grader did not return valid JSON: {raw[:200]!r}",
        }

    if "pass" not in parsed:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Grader response is missing a 'pass' field: {raw[:200]!r}",
        }

    passed = bool(parsed["pass"])
    reason = parsed.get("reason", "(grader gave no reason)")
    return {"pass": passed, "score": 1.0 if passed else 0.0, "reason": f"[LLM-judge, {model}] {reason}"}
