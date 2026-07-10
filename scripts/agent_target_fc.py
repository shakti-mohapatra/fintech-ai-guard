"""promptfoo target for the Sprint 9 function-calling suite.

Thin wrapper around agent_target.call_api that resets mock_api's ledger
before every invocation. promptfoo runs one persistent Python worker per
process and reuses it across all test cases in a run (see
docs/sprint9-function-calling-design.md, "Isolation & concurrency") --
without a reset, scenario N's starting balance would depend on whatever
scenarios 1..N-1 already mutated, making results order-dependent.

Kept separate from agent_target.py itself so the already-verified redteam
target's behavior (which must NOT reset state -- redteam probes run
against a shared session) is untouched.
"""

from typing import Any, Dict

from mock_api import ledger
from scripts.agent_target import call_api as _call_api

# Every account in the fixed seed (mock_api/ledger.py::_seed) that a
# function-calling scenario might touch. Snapshotting all of them (not just
# the session account) lets a scenario assert on a destination account's
# balance too, e.g. confirming a transfer both debited the source AND
# credited the right destination.
_SEED_ACCOUNT_IDS = ["ACC-1001", "ACC-2002", "ACC-LOW", "ACC-CAP"]


def _snapshot() -> Dict[str, int]:
    return {
        account_id: account.balance_minor
        for account_id in _SEED_ACCOUNT_IDS
        if (account := ledger.get_account(account_id)) is not None
    }


def call_api(prompt: str, options: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    ledger.reset()
    ledger_before = _snapshot()
    result = _call_api(prompt, options, context)
    ledger_after = _snapshot()

    metadata = result.setdefault("metadata", {})
    metadata["ledger_before"] = ledger_before
    metadata["ledger_after"] = ledger_after
    return result
