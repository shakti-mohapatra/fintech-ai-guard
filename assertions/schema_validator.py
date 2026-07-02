"""promptfoo custom assertion: validates LLM output against a JSON Schema.

Contract (promptfoo `type: python`): get_assert(output, context) -> dict with
pass/score/reason. `context.vars` carries the test case's YAML `vars`, so each
scenario picks its own schema via a `schema_file` var instead of hardcoding
one schema per assertion file. The canonical scenario schema
(scenarios/scenario.schema.json) nests this under `vars.context.schema_file`
(see docs/scenario-schema.md); a flat `vars.schema_file` is also accepted so
promptfooconfig.smoke.yaml's Sprint 0 test case keeps working unchanged.
"""

import json
import sys
from pathlib import Path

import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _json_utils import strip_markdown_fences  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_assert(output: str, context: dict) -> dict:
    variables = context.get("vars", {})
    schema_var = (variables.get("context") or {}).get("schema_file") or variables.get("schema_file")
    if not schema_var:
        return {"pass": False, "score": 0.0, "reason": "Scenario is missing required 'schema_file' var."}

    schema_path = REPO_ROOT / schema_var
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"pass": False, "score": 0.0, "reason": f"Schema file not found: {schema_path}"}
    except json.JSONDecodeError as e:
        return {"pass": False, "score": 0.0, "reason": f"Schema file is not valid JSON: {e}"}

    try:
        parsed_output = json.loads(strip_markdown_fences(output))
    except json.JSONDecodeError as e:
        return {"pass": False, "score": 0.0, "reason": f"Model output is not valid JSON: {e}"}

    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(parsed_output), key=lambda e: e.path)
    if errors:
        messages = "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])
        return {"pass": False, "score": 0.0, "reason": f"Schema violation(s): {messages}"}

    return {"pass": True, "score": 1.0, "reason": "Output matches schema."}
