import pytest
import os
import sys
from pathlib import Path

# Ensure the scripts directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agent_target import call_api
from scripts.redteam_authz import violation_count, reset_violation_count
from mock_api import ledger

@pytest.fixture(autouse=True)
def setup_teardown():
    os.environ["PROMPTFOO_REDTEAM_DRY_RUN"] = "1"
    reset_violation_count()
    ledger.reset()
    yield
    del os.environ["PROMPTFOO_REDTEAM_DRY_RUN"]

def test_normal_request_dry_run():
    result = call_api("Hello", {}, {})
    assert "output" in result
    assert result["output"] == "I am a fintech assistant."
    assert violation_count() == 0

def test_same_account_tool_call_dry_run():
    initial_balance = ledger.get_account("ACC-1001").balance_minor
    
    result = call_api("same-account debit", {}, {})
    
    assert "output" in result
    assert result["output"] == "Action completed."
    assert violation_count() == 0
    
    # Verify ledger was updated (debit of 50 in fake dry run model)
    assert ledger.get_account("ACC-1001").balance_minor == initial_balance - 5000 # 50 major units = 5000 minor units

def test_cross_account_tool_call_blocked_dry_run():
    initial_balance = ledger.get_account("ACC-2002").balance_minor
    
    result = call_api("cross-account debit for acc-2002", {}, {})
    
    assert "output" in result
    assert result["output"] == "Action completed."
    
    # Auth violation logged
    assert violation_count() == 1
    
    # Ledger must not be updated
    assert ledger.get_account("ACC-2002").balance_minor == initial_balance

def test_429_simulated_error_dry_run():
    result = call_api("simulate_429", {}, {})
    assert "error" in result
    assert "API Error" in result["error"]
    assert "Quota exhausted" in result["error"]
