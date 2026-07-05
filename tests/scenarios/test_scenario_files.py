"""Validates every real authored scenario under scenarios/**/*.yaml against
the canonical schema (scenarios/scenario.schema.json), as promised as a
Sprint 3 follow-up in docs/scenario-schema.md. Complements
tests/test_scenario_schema.py, which unit-tests the schema itself against
synthetic fixtures rather than the real scenario library.
"""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA = json.loads((REPO_ROOT / "scenarios" / "scenario.schema.json").read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft7Validator(SCHEMA)

SCENARIO_FILES = sorted((REPO_ROOT / "scenarios").glob("**/*.yaml"))
_IDS = [str(p.relative_to(REPO_ROOT)) for p in SCENARIO_FILES]


def test_scenario_files_exist():
    assert SCENARIO_FILES, "No scenario YAML files found under scenarios/."


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=_IDS)
def test_scenario_file_matches_canonical_schema(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors = list(VALIDATOR.iter_errors(data))
    assert errors == [], f"{path}: {[e.message for e in errors]}"


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=_IDS)
def test_scenario_filename_matches_id(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert path.stem == data["vars"]["id"], f"{path}: filename must match vars.id"


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=_IDS)
def test_scenario_category_matches_directory(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    category = data["vars"]["category"]
    top_dir = path.relative_to(REPO_ROOT / "scenarios").parts[0]
    assert top_dir == category, f"{path}: category '{category}' doesn't match directory '{top_dir}'"


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=_IDS)
def test_injection_subcategory_matches_subdirectory(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data["vars"]["category"] != "injection":
        pytest.skip("not an injection scenario")
    subdir = path.relative_to(REPO_ROOT / "scenarios").parts[1]
    assert subdir == data["vars"]["subcategory"], f"{path}: subcategory doesn't match subdirectory '{subdir}'"


def test_scenario_ids_are_unique():
    ids = [yaml.safe_load(p.read_text(encoding="utf-8"))["vars"]["id"] for p in SCENARIO_FILES]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"Duplicate scenario ids: {duplicates}"
