import pytest
import sys
import importlib
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

def test_file_handler_added_when_env_var_set(tmp_path, monkeypatch):
    """REDTEAM_AUTHZ_LOG_PATH must add a FileHandler that writes real jsonl."""
    import scripts.redteam_authz as ra_module

    log_file = tmp_path / "redteam-authz.jsonl"
    monkeypatch.setenv("REDTEAM_AUTHZ_LOG_PATH", str(log_file))

    logger = logging.getLogger("redteam.authz")
    original_handlers = list(logger.handlers)
    for h in original_handlers:
        logger.removeHandler(h)

    try:
        importlib.reload(ra_module)

        result = ra_module.guarded_tool_call(
            tool_name="debit",
            account_id="ACC-2002",
            fn=stub_fn,
            amount=100,
            currency="USD",
            prompt_excerpt="cross-account probe",
        )
        assert result["error"] == "authorization_boundary"

        assert log_file.exists()
        lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event"] == "authorization_violation_attempt"
        assert event["requested_account_id"] == "ACC-2002"
    finally:
        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()
        monkeypatch.delenv("REDTEAM_AUTHZ_LOG_PATH", raising=False)
        importlib.reload(ra_module)
        # Reloading rebinds module-level names in ra_module; the package-level
        # import used by the rest of this test file (`from scripts.redteam_authz
        # import ...`) still points at the pre-reload functions, which is fine
        # since they close over the same singleton `redteam.authz` logger.
