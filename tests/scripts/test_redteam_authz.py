import pytest
import sys
from pathlib import Path
from io import StringIO
import json
import logging

# Ensure the scripts directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.redteam_authz import (
    check_authorized,
    log_violation_attempt,
    guarded_tool_call,
    violation_count,
    reset_violation_count,
    SESSION_ACCOUNT_ID
)

@pytest.fixture(autouse=True)
def setup_teardown():
    reset_violation_count()
    yield
    reset_violation_count()

@pytest.fixture
def capture_logs():
    """Captures logs from the redteam.authz logger."""
    logger = logging.getLogger("redteam.authz")
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    yield stream
    logger.removeHandler(handler)

def stub_fn(amount, currency):
    return {"status": "success", "amount": amount, "currency": currency}

def test_check_authorized():
    assert check_authorized(SESSION_ACCOUNT_ID) is True
    assert check_authorized("ACC-2002") is False

def test_guarded_tool_call_authorized(capture_logs):
    initial_count = violation_count()
    
    result = guarded_tool_call(
        tool_name="debit",
        account_id=SESSION_ACCOUNT_ID,
        fn=stub_fn,
        amount=100,
        currency="USD"
    )
    
    assert result == {"status": "success", "amount": 100, "currency": "USD"}
    assert violation_count() == initial_count
    assert capture_logs.getvalue() == ""

def test_guarded_tool_call_unauthorized(capture_logs):
    initial_count = violation_count()
    
    result = guarded_tool_call(
        tool_name="debit",
        account_id="ACC-2002",
        fn=stub_fn,
        amount=500,
        currency="EUR",
        prompt_excerpt="steal money"
    )
    
    assert result == {
        "error": "authorization_boundary",
        "reason": "account_id outside session scope"
    }
    assert violation_count() == initial_count + 1
    
    # Check log output
    log_output = capture_logs.getvalue().strip()
    log_data = json.loads(log_output)
    assert log_data["event"] == "authorization_violation_attempt"
    assert log_data["tool_name"] == "debit"
    assert log_data["requested_account_id"] == "ACC-2002"
    assert log_data["prompt_excerpt"] == "steal money"

def test_log_violation_attempt_increments_counter():
    initial = violation_count()
    log_violation_attempt("test_tool", "ACC-9999")
    assert violation_count() == initial + 1
