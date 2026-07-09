import json
import logging
import os
import sys
from pathlib import Path

SESSION_ACCOUNT_ID = "ACC-1001"

_violation_counter = 0

# Set up the logger
logger = logging.getLogger("redteam.authz")
logger.setLevel(logging.INFO)
# Avoid adding multiple handlers if this module is reloaded in tests
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    logger.addHandler(handler)
    # Opt-in file sink for a live redteam run (scripts/generate_redteam_report.py's
    # optional authz-log argument reads this back to independently confirm
    # BOLA/BFLA structural blocks). Unset during pytest, so unit-test
    # violations never land in a "real run" log file.
    log_path = os.environ.get("REDTEAM_AUTHZ_LOG_PATH")
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        logger.addHandler(file_handler)
# Do not propagate to root logger to avoid duplicate logs in the main app
logger.propagate = False

def check_authorized(requested_account_id: str) -> bool:
    """Pure, deterministic check if an account is authorized for this session."""
    return requested_account_id == SESSION_ACCOUNT_ID

def log_violation_attempt(tool_name: str, requested_account_id: str, prompt_excerpt: str = "") -> None:
    """Emits a structured JSON line to a redteam.authz logger."""
    global _violation_counter
    _violation_counter += 1
    
    event = {
        "event": "authorization_violation_attempt",
        "tool_name": tool_name,
        "requested_account_id": requested_account_id,
        "prompt_excerpt": prompt_excerpt,
    }
    logger.info(json.dumps(event))

def guarded_tool_call(tool_name: str, account_id: str, fn, *args, **kwargs):
    """
    If account_id != SESSION_ACCOUNT_ID, logs the violation attempt and 
    returns a synthetic rejection without calling fn.
    Otherwise calls fn normally and returns its result.
    """
    if not check_authorized(account_id):
        prompt_excerpt = kwargs.pop("prompt_excerpt", "")
        log_violation_attempt(tool_name, account_id, prompt_excerpt)
        return {
            "error": "authorization_boundary",
            "reason": "account_id outside session scope"
        }
    
    # Exclude prompt_excerpt if it was passed to guarded_tool_call but isn't for the inner fn
    kwargs.pop("prompt_excerpt", None)
    return fn(*args, **kwargs)

def violation_count() -> int:
    """Returns how many blocks happened in the current process."""
    return _violation_counter

def reset_violation_count() -> None:
    """Resets the violation counter, mainly for testing purposes."""
    global _violation_counter
    _violation_counter = 0
