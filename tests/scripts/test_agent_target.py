import json
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

def test_transfer_tool_call_dry_run():
    result = call_api("transfer-test", {}, {})

    assert "output" in result
    assert result["output"] == "Action completed."
    assert violation_count() == 0

    # Real ledger side effect: ACC-1001 -$10, ACC-LOW +$10 (1000 minor units)
    assert ledger.get_account("ACC-1001").balance_minor == 100_000 - 1000
    assert ledger.get_account("ACC-LOW").balance_minor == 1_000 + 1000

def test_call_api_returns_tool_call_trace_metadata():
    result = call_api("transfer-test", {}, {})

    assert "metadata" in result
    trace = result["metadata"]["tool_calls"]
    assert len(trace) == 1
    assert trace[0]["name"] == "transfer_tool"
    assert trace[0]["args"]["destination_account_id"] == "ACC-LOW"
    tool_result = json.loads(trace[0]["result"])
    assert tool_result["reason_code"] == "APPROVED"

def test_normal_request_dry_run_has_empty_trace():
    result = call_api("Hello", {}, {})
    assert result["metadata"]["tool_calls"] == []
