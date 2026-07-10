import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agent_target_fc import call_api
from scripts.redteam_authz import reset_violation_count
from mock_api import ledger


@pytest.fixture(autouse=True)
def setup_teardown():
    os.environ["PROMPTFOO_REDTEAM_DRY_RUN"] = "1"
    reset_violation_count()
    yield
    del os.environ["PROMPTFOO_REDTEAM_DRY_RUN"]


def test_resets_ledger_before_running():
    # Mutate the ledger away from the seed, then confirm call_api resets it
    # back before executing the scenario -- proves scenario order can't
    # leak state between test cases in one promptfoo run.
    ledger.get_account("ACC-1001").balance_minor = 1
    result = call_api("Hello", {}, {})
    assert result["metadata"]["ledger_before"]["ACC-1001"] == 100_000


def test_ledger_before_and_after_reflect_real_transfer():
    result = call_api("transfer-test", {}, {})

    assert result["metadata"]["ledger_before"]["ACC-1001"] == 100_000
    assert result["metadata"]["ledger_before"]["ACC-LOW"] == 1_000
    assert result["metadata"]["ledger_after"]["ACC-1001"] == 100_000 - 1000
    assert result["metadata"]["ledger_after"]["ACC-LOW"] == 1_000 + 1000


def test_no_side_effect_scenario_has_matching_before_after():
    result = call_api("Hello", {}, {})
    assert result["metadata"]["ledger_before"] == result["metadata"]["ledger_after"]
