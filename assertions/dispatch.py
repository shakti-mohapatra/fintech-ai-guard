"""promptfoo custom assertion: routes each scenario to its category's
assertion module.

Contract (promptfoo `type: python`): get_assert(output, context) -> dict.
Wired once via `defaultTest.assert` in promptfooconfig.js rather than
per-scenario, per the design decision in docs/scenario-schema.md (scenario
YAML files deliberately carry no assert: block — see "Not part of this
schema" there). Adding a category or renaming an assertion module only
requires touching the map below.
"""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_CATEGORY_MODULE = {
    "hallucination": "hallucination_check",
    "injection": "injection_resistance",
    "schema-compliance": "schema_validator",
    "numeric-precision": "numeric_precision",
    "logic-consistency": "logic_consistency",
    "idempotency": "idempotency_check",
    "pii-pci": "pii_leakage",
    "l3-data-extraction": "schema_validator",  # + numeric_precision below
    "tone-disclosure": "tone_rubric",
}

# L3 extraction reconciles arithmetic in addition to schema shape
# (docs/test-strategy.md category 8), whenever the scenario supplies the
# numeric_precision context keys.
_L3_NUMERIC_MODULE = "numeric_precision"


def get_assert(output: str, context: dict) -> dict:
    variables = context.get("vars", {})
    category = variables.get("category")
    module_name = _CATEGORY_MODULE.get(category)

    if module_name is None:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"No assertion wired for category '{category}' in assertions/dispatch.py.",
        }

    module = importlib.import_module(module_name)
    result = module.get_assert(output, context)

    if category == "l3-data-extraction" and result.get("pass"):
        ctx = variables.get("context", {}) or {}
        if "expected_total" in ctx or "components" in ctx:
            numeric_module = importlib.import_module(_L3_NUMERIC_MODULE)
            numeric_result = numeric_module.get_assert(output, context)
            if not numeric_result.get("pass"):
                return numeric_result

    return result
