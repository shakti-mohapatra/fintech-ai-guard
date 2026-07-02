"""promptfoo custom assertion: flags hallucinated facts in LLM output.

Contract (promptfoo `type: python`): get_assert(output, context) -> dict.
Ground truth is reference-anchored (docs/test-strategy.md): every
date/amount/reference-number-shaped token in `output` must be traceable
back to the scenario's own `input` (and `context`, if present) — anything
else is treated as a fabricated fact. Backstopped by an explicit
`forbidden_patterns` check for trap types (e.g. invented entity names)
that verbatim fact-tracing can't catch on its own.
"""

import json
import re

DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # 2026-07-02
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),  # 7/2/2026
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE,
    ),
]
AMOUNT_PATTERN = re.compile(
    r"(?:USD|EUR|GBP|\$|€|£)\s?\d[\d,]*\.\d{2}|\d[\d,]*\.\d{2}\s?(?:USD|EUR|GBP)"
)
REFERENCE_NUMBER_PATTERN = re.compile(r"\b\d{6,}\b")

FACT_PATTERNS = DATE_PATTERNS + [AMOUNT_PATTERN, REFERENCE_NUMBER_PATTERN]


def _normalize(text: str) -> str:
    return re.sub(r"[,\s]", "", text).lower()


def _source_text(context: dict) -> str:
    variables = context.get("vars", {})
    parts = [str(variables.get("input", ""))]
    ctx = variables.get("context")
    if ctx:
        parts.append(json.dumps(ctx))
    return " ".join(parts)


def get_assert(output: str, context: dict) -> dict:
    variables = context.get("vars", {})
    forbidden = variables.get("forbidden_patterns", [])

    for pattern in forbidden:
        if re.search(pattern, output):
            return {
                "pass": False,
                "score": 0.0,
                "reason": f"Output matches forbidden pattern '{pattern}' (likely fabricated content).",
            }

    source = _normalize(_source_text(context))
    unsourced = set()
    for pattern in FACT_PATTERNS:
        for match in pattern.finditer(output):
            token = match.group(0)
            if _normalize(token) not in source:
                unsourced.add(token)

    if unsourced:
        preview = ", ".join(sorted(unsourced)[:5])
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Output contains fact(s) not traceable to the scenario input/context: {preview}",
        }

    return {
        "pass": True,
        "score": 1.0,
        "reason": "All dates/amounts/reference numbers in output trace back to source.",
    }
