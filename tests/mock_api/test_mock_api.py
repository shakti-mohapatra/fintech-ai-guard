import logging
import sys
import threading
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from mock_api import ledger  # noqa: E402
from mock_api.app import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_ledger():
    ledger.reset()
    yield
    ledger.reset()


def _bal(account_id: str) -> Decimal:
    body = client.get(f"/balance/{account_id}").json()
    return Decimal(str(body["balance"]))


# --- health & balance -------------------------------------------------------

def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_balance_known_account():
    body = client.get("/balance/ACC-1001").json()
    assert body["currency"] == "USD"
    assert Decimal(str(body["balance"])) == Decimal("1000.00")


def test_balance_unknown_account_404():
    assert client.get("/balance/NOPE").status_code == 404


# --- debit happy path & validation -----------------------------------------

def test_debit_success_moves_money_once():
    resp = client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "10.00", "currency": "USD", "reference_id": "D1"},
    ).json()
    assert resp["action"] == "debit"
    assert resp["reason_code"] == "APPROVED"
    assert Decimal(str(resp["resulting_balance"])) == Decimal("990.00")
    assert _bal("ACC-1001") == Decimal("990.00")


def test_debit_zero_amount_rejected():
    resp = client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "0.00", "currency": "USD", "reference_id": "D0"},
    ).json()
    assert resp["action"] == "reject"
    assert resp["reason_code"] == "INVALID_AMOUNT"
    assert _bal("ACC-1001") == Decimal("1000.00")


def test_debit_negative_amount_rejected():
    resp = client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "-50.00", "currency": "USD", "reference_id": "DN"},
    ).json()
    assert resp["action"] == "reject"
    assert resp["reason_code"] == "INVALID_AMOUNT"
    assert _bal("ACC-1001") == Decimal("1000.00")


def test_debit_more_than_two_decimals_is_422():
    r = client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "10.001", "currency": "USD", "reference_id": "DX"},
    )
    assert r.status_code == 422


def test_debit_unknown_account_rejected():
    resp = client.post(
        "/debit",
        json={"account_id": "GHOST", "amount": "10.00", "currency": "USD", "reference_id": "DG"},
    ).json()
    assert resp["reason_code"] == "UNKNOWN_ACCOUNT"


def test_debit_currency_mismatch_rejected():
    resp = client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "10.00", "currency": "EUR", "reference_id": "DC"},
    ).json()
    assert resp["reason_code"] == "CURRENCY_MISMATCH"
    assert _bal("ACC-1001") == Decimal("1000.00")


def test_debit_daily_limit_exceeded_rejected():
    # ACC-CAP has a 2500.00 daily limit but 10000.00 balance — isolates the
    # limit check from the funds check.
    resp = client.post(
        "/debit",
        json={"account_id": "ACC-CAP", "amount": "3000.00", "currency": "USD", "reference_id": "DL"},
    ).json()
    assert resp["reason_code"] == "DAILY_LIMIT_EXCEEDED"
    assert _bal("ACC-CAP") == Decimal("10000.00")


def test_debit_insufficient_funds_rejected():
    resp = client.post(
        "/debit",
        json={"account_id": "ACC-LOW", "amount": "50.00", "currency": "USD", "reference_id": "DF"},
    ).json()
    assert resp["reason_code"] == "INSUFFICIENT_FUNDS"
    assert _bal("ACC-LOW") == Decimal("10.00")


# --- duplicate & idempotency safety ----------------------------------------

def test_duplicate_reference_rejected_and_charged_once():
    body = {"account_id": "ACC-1001", "amount": "100.00", "currency": "USD", "reference_id": "DUP"}
    first = client.post("/debit", json=body).json()
    second = client.post("/debit", json=body).json()
    assert first["action"] == "debit"
    assert second["action"] == "reject"
    assert second["reason_code"] == "DUPLICATE_SUBMISSION"
    assert _bal("ACC-1001") == Decimal("900.00")  # charged exactly once


def test_idempotency_key_replay_does_not_double_charge():
    body = {
        "account_id": "ACC-1001",
        "amount": "100.00",
        "currency": "USD",
        "reference_id": "IDEMP-REF",
        "idempotency_key": "KEY-1",
    }
    first = client.post("/debit", json=body).json()
    second = client.post("/debit", json=body).json()
    assert first["action"] == "debit"
    assert first["idempotent_replay"] is False
    assert second["action"] == "debit"  # same result, not a rejection
    assert second["idempotent_replay"] is True
    assert _bal("ACC-1001") == Decimal("900.00")  # charged exactly once


# --- refund: the flagship guarantee ----------------------------------------

def test_refund_credits_balance_and_never_debits():
    client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "200.00", "currency": "USD", "reference_id": "ORIG-1"},
    )
    assert _bal("ACC-1001") == Decimal("800.00")

    resp = client.post(
        "/refund",
        json={
            "account_id": "ACC-1001",
            "amount": "200.00",
            "currency": "USD",
            "reference_id": "REF-1",
            "original_reference_id": "ORIG-1",
        },
    ).json()
    assert resp["action"] == "refund"  # never "debit"
    assert resp["reason_code"] == "CUSTOMER_REQUEST"
    # Balance went UP, back to the starting point — a refund credits.
    assert _bal("ACC-1001") == Decimal("1000.00")


def test_refund_does_not_touch_daily_debited():
    client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "200.00", "currency": "USD", "reference_id": "ORIG-2"},
    )
    before = client.get("/balance/ACC-1001").json()
    assert Decimal(str(before["daily_debited"])) == Decimal("200.00")
    client.post(
        "/refund",
        json={
            "account_id": "ACC-1001",
            "amount": "200.00",
            "currency": "USD",
            "reference_id": "REF-2",
            "original_reference_id": "ORIG-2",
        },
    )
    after = client.get("/balance/ACC-1001").json()
    # A refund is not a negative debit — daily_debited is unchanged.
    assert Decimal(str(after["daily_debited"])) == Decimal("200.00")


def test_refund_without_original_rejected():
    resp = client.post(
        "/refund",
        json={
            "account_id": "ACC-1001",
            "amount": "50.00",
            "currency": "USD",
            "reference_id": "REF-NO",
            "original_reference_id": "DOES-NOT-EXIST",
        },
    ).json()
    assert resp["reason_code"] == "NO_ORIGINAL_TRANSACTION"


def test_refund_exceeding_original_rejected():
    client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "100.00", "currency": "USD", "reference_id": "ORIG-3"},
    )
    resp = client.post(
        "/refund",
        json={
            "account_id": "ACC-1001",
            "amount": "150.00",
            "currency": "USD",
            "reference_id": "REF-3",
            "original_reference_id": "ORIG-3",
        },
    ).json()
    assert resp["reason_code"] == "REFUND_EXCEEDS_ORIGINAL"


def test_partial_refunds_within_original_then_over_rejected():
    client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "100.00", "currency": "USD", "reference_id": "ORIG-4"},
    )
    ok1 = client.post(
        "/refund",
        json={"account_id": "ACC-1001", "amount": "60.00", "currency": "USD",
              "reference_id": "REF-4A", "original_reference_id": "ORIG-4"},
    ).json()
    ok2 = client.post(
        "/refund",
        json={"account_id": "ACC-1001", "amount": "40.00", "currency": "USD",
              "reference_id": "REF-4B", "original_reference_id": "ORIG-4"},
    ).json()
    over = client.post(
        "/refund",
        json={"account_id": "ACC-1001", "amount": "0.01", "currency": "USD",
              "reference_id": "REF-4C", "original_reference_id": "ORIG-4"},
    ).json()
    assert ok1["action"] == "refund"
    assert ok2["action"] == "refund"
    assert over["reason_code"] == "REFUND_EXCEEDS_ORIGINAL"


def test_refund_idempotency_key_replay_credits_once():
    client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "100.00", "currency": "USD", "reference_id": "ORIG-5"},
    )
    body = {
        "account_id": "ACC-1001",
        "amount": "100.00",
        "currency": "USD",
        "reference_id": "REF-5",
        "original_reference_id": "ORIG-5",
        "idempotency_key": "RKEY-1",
    }
    client.post("/refund", json=body)
    second = client.post("/refund", json=body).json()
    assert second["idempotent_replay"] is True
    # Debit -100 then a single +100 refund -> back to 1000.00, credited once.
    assert _bal("ACC-1001") == Decimal("1000.00")


# --- transfer -------------------------------------------------------------

def test_transfer_success():
    resp = client.post(
        "/transfer",
        json={"source_account_id": "ACC-1001", "destination_account_id": "ACC-CAP", "amount": "50.00", "currency": "USD", "reference_id": "T1"}
    ).json()
    assert resp["action"] == "transfer"
    assert resp["reason_code"] == "APPROVED"
    assert _bal("ACC-1001") == Decimal("950.00")
    assert _bal("ACC-CAP") == Decimal("10050.00")

def test_transfer_currency_mismatch():
    resp = client.post(
        "/transfer",
        json={"source_account_id": "ACC-1001", "destination_account_id": "ACC-2002", "amount": "50.00", "currency": "USD", "reference_id": "T2"}
    ).json()
    assert resp["reason_code"] == "CURRENCY_MISMATCH"

def test_transfer_success_same_currency():
    resp = client.post(
        "/transfer",
        json={"source_account_id": "ACC-1001", "destination_account_id": "ACC-LOW", "amount": "50.00", "currency": "USD", "reference_id": "T3"}
    ).json()
    assert resp["action"] == "transfer"
    assert resp["reason_code"] == "APPROVED"
    assert _bal("ACC-1001") == Decimal("950.00")
    assert _bal("ACC-LOW") == Decimal("60.00")

def test_transfer_insufficient_funds():
    resp = client.post(
        "/transfer",
        json={"source_account_id": "ACC-LOW", "destination_account_id": "ACC-1001", "amount": "50.00", "currency": "USD", "reference_id": "T4"}
    ).json()
    assert resp["reason_code"] == "INSUFFICIENT_FUNDS"
    assert _bal("ACC-LOW") == Decimal("10.00")

# --- Sprint 12 / docs/sprint11-test-hardening-plan.md §2A ------------------
# Request-validation, exact-boundary, error-handling, transfer negative-path
# parity, concurrency, and audit-log leakage coverage. debit/refund already
# had solid business-logic coverage above; transfer (added later, Sprint 9)
# had not caught up to debit/refund's negative-path depth until this batch.

# --- request validation: missing/wrong-type/extra fields, malformed shapes -

def test_debit_missing_required_field_422():
    r = client.post("/debit", json={"account_id": "ACC-1001", "currency": "USD", "reference_id": "V1"})
    assert r.status_code == 422


def test_debit_wrong_type_amount_422():
    r = client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": True, "currency": "USD", "reference_id": "V2"},
    )
    assert r.status_code == 422


def test_debit_extra_field_rejected_422():
    r = client.post(
        "/debit",
        json={
            "account_id": "ACC-1001",
            "amount": "10.00",
            "currency": "USD",
            "reference_id": "V3",
            "unexpected_field": "should not be allowed",
        },
    )
    assert r.status_code == 422


@pytest.mark.parametrize("currency", ["usd", "US", "1234", "US1"])
def test_debit_invalid_currency_shape_422(currency):
    r = client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "10.00", "currency": currency, "reference_id": f"V-CUR-{currency}"},
    )
    assert r.status_code == 422


def test_debit_empty_account_id_422():
    r = client.post("/debit", json={"account_id": "", "amount": "10.00", "currency": "USD", "reference_id": "V4"})
    assert r.status_code == 422


def test_debit_empty_reference_id_422():
    r = client.post("/debit", json={"account_id": "ACC-1001", "amount": "10.00", "currency": "USD", "reference_id": ""})
    assert r.status_code == 422


def test_debit_malformed_json_body_422():
    r = client.post(
        "/debit",
        content=b'{"account_id": "ACC-1001", "amount": "10.00", "currency": "USD", "reference_id": ',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_debit_wrong_http_method_405():
    r = client.get("/debit")
    assert r.status_code == 405


def test_balance_injection_shaped_account_id_is_404_not_500():
    # In-memory ledger lookup is a plain dict.get — proving this returns a
    # clean 404 (not a 500) for a hostile-shaped path segment is a cheap,
    # concrete demonstration that there's no SQL/path-traversal surface here.
    r = client.get("/balance/'; DROP TABLE accounts;--")
    assert r.status_code == 404


# --- exact-boundary amounts (the actual boundary, not just over/under it) --

def test_debit_amount_exactly_equals_remaining_daily_limit_is_approved():
    # ACC-CAP: daily_limit 2500.00, 0.00 debited so far this test run.
    resp = client.post(
        "/debit",
        json={"account_id": "ACC-CAP", "amount": "2500.00", "currency": "USD", "reference_id": "BND-1"},
    ).json()
    assert resp["action"] == "debit"
    assert resp["reason_code"] == "APPROVED"


def test_debit_amount_exactly_equals_balance_is_approved_and_drains_to_zero():
    # ACC-LOW: balance exactly 10.00.
    resp = client.post(
        "/debit",
        json={"account_id": "ACC-LOW", "amount": "10.00", "currency": "USD", "reference_id": "BND-2"},
    ).json()
    assert resp["action"] == "debit"
    assert resp["reason_code"] == "APPROVED"
    assert _bal("ACC-LOW") == Decimal("0.00")


def test_debit_amount_one_cent_over_balance_is_insufficient_funds():
    resp = client.post(
        "/debit",
        json={"account_id": "ACC-LOW", "amount": "10.01", "currency": "USD", "reference_id": "BND-3"},
    ).json()
    assert resp["reason_code"] == "INSUFFICIENT_FUNDS"
    assert _bal("ACC-LOW") == Decimal("10.00")


# --- concurrency: proves the lock actually serializes -----------------------

def test_concurrent_identical_retry_charges_exactly_once():
    # Two threads submit the literal same retry (same reference_id AND same
    # idempotency_key) as close to simultaneously as possible. If the lock
    # only protected sequential calls (and not real concurrent contention),
    # this is where a race would show up as a double debit.
    body = {
        "account_id": "ACC-1001",
        "amount": "100.00",
        "currency": "USD",
        "reference_id": "RACE-1",
        "idempotency_key": "RACE-KEY-1",
    }
    barrier = threading.Barrier(2)
    results = [None, None]

    def _call(i):
        barrier.wait(timeout=5)
        results[i] = client.post("/debit", json=body).json()

    t1 = threading.Thread(target=_call, args=(0,))
    t2 = threading.Thread(target=_call, args=(1,))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    actions = sorted(r["action"] for r in results)
    # Exactly one real debit; the other must be either the idempotent replay
    # of the same response, or a DUPLICATE_SUBMISSION reject via reference_id
    # — either way, never a second real charge.
    assert actions.count("debit") <= 2  # both may report "debit" if one is idempotent_replay
    replay_flags = [r.get("idempotent_replay", False) for r in results]
    reason_codes = [r["reason_code"] for r in results]
    assert (
        any(replay_flags)
        or "DUPLICATE_SUBMISSION" in reason_codes
    ), f"Neither an idempotent replay nor a duplicate rejection occurred: {results}"
    # The financial invariant that actually matters: charged exactly once.
    assert _bal("ACC-1001") == Decimal("900.00")


# --- refund: negative-path additions ----------------------------------------

def test_refund_missing_original_reference_id_422():
    r = client.post(
        "/refund",
        json={"account_id": "ACC-1001", "amount": "10.00", "currency": "USD", "reference_id": "RF-V1"},
    )
    assert r.status_code == 422


def test_refund_unknown_account_rejected():
    resp = client.post(
        "/refund",
        json={
            "account_id": "GHOST",
            "amount": "10.00",
            "currency": "USD",
            "reference_id": "RF-V2",
            "original_reference_id": "DOESNT-MATTER",
        },
    ).json()
    assert resp["reason_code"] == "UNKNOWN_ACCOUNT"


def test_refund_currency_mismatch_rejected():
    client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "100.00", "currency": "USD", "reference_id": "RF-ORIG-CM"},
    )
    resp = client.post(
        "/refund",
        json={
            "account_id": "ACC-1001",
            "amount": "100.00",
            "currency": "EUR",
            "reference_id": "RF-V3",
            "original_reference_id": "RF-ORIG-CM",
        },
    ).json()
    assert resp["reason_code"] == "CURRENCY_MISMATCH"


def test_refund_zero_amount_rejected():
    client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "100.00", "currency": "USD", "reference_id": "RF-ORIG-Z"},
    )
    resp = client.post(
        "/refund",
        json={
            "account_id": "ACC-1001",
            "amount": "0.00",
            "currency": "USD",
            "reference_id": "RF-V4",
            "original_reference_id": "RF-ORIG-Z",
        },
    ).json()
    assert resp["reason_code"] == "INVALID_AMOUNT"


def test_refund_negative_amount_rejected():
    client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "100.00", "currency": "USD", "reference_id": "RF-ORIG-N"},
    )
    resp = client.post(
        "/refund",
        json={
            "account_id": "ACC-1001",
            "amount": "-10.00",
            "currency": "USD",
            "reference_id": "RF-V5",
            "original_reference_id": "RF-ORIG-N",
        },
    ).json()
    assert resp["reason_code"] == "INVALID_AMOUNT"


def test_refund_duplicate_reference_rejected_without_idempotency_key():
    client.post(
        "/debit",
        json={"account_id": "ACC-1001", "amount": "100.00", "currency": "USD", "reference_id": "RF-ORIG-DUP"},
    )
    body = {
        "account_id": "ACC-1001",
        "amount": "50.00",
        "currency": "USD",
        "reference_id": "RF-V6",
        "original_reference_id": "RF-ORIG-DUP",
    }
    first = client.post("/refund", json=body).json()
    second = client.post("/refund", json=body).json()
    assert first["action"] == "refund"
    assert second["reason_code"] == "DUPLICATE_SUBMISSION"


# --- transfer: negative-path parity with debit/refund -----------------------

def test_transfer_same_account_rejected():
    resp = client.post(
        "/transfer",
        json={
            "source_account_id": "ACC-1001",
            "destination_account_id": "ACC-1001",
            "amount": "10.00",
            "currency": "USD",
            "reference_id": "TX-V1",
        },
    ).json()
    assert resp["reason_code"] == "SAME_ACCOUNT_TRANSFER"


def test_transfer_unknown_source_account_rejected():
    resp = client.post(
        "/transfer",
        json={
            "source_account_id": "GHOST",
            "destination_account_id": "ACC-1001",
            "amount": "10.00",
            "currency": "USD",
            "reference_id": "TX-V2",
        },
    ).json()
    assert resp["reason_code"] == "UNKNOWN_ACCOUNT"


def test_transfer_unknown_destination_account_rejected():
    resp = client.post(
        "/transfer",
        json={
            "source_account_id": "ACC-1001",
            "destination_account_id": "GHOST",
            "amount": "10.00",
            "currency": "USD",
            "reference_id": "TX-V3",
        },
    ).json()
    assert resp["reason_code"] == "UNKNOWN_ACCOUNT"


def test_transfer_zero_amount_rejected():
    resp = client.post(
        "/transfer",
        json={
            "source_account_id": "ACC-1001",
            "destination_account_id": "ACC-CAP",
            "amount": "0.00",
            "currency": "USD",
            "reference_id": "TX-V4",
        },
    ).json()
    assert resp["reason_code"] == "INVALID_AMOUNT"


def test_transfer_more_than_two_decimals_is_422():
    r = client.post(
        "/transfer",
        json={
            "source_account_id": "ACC-1001",
            "destination_account_id": "ACC-CAP",
            "amount": "10.001",
            "currency": "USD",
            "reference_id": "TX-V5",
        },
    )
    assert r.status_code == 422


def test_transfer_daily_limit_exceeded_rejected():
    resp = client.post(
        "/transfer",
        json={
            "source_account_id": "ACC-CAP",
            "destination_account_id": "ACC-1001",
            "amount": "3000.00",
            "currency": "USD",
            "reference_id": "TX-V6",
        },
    ).json()
    assert resp["reason_code"] == "DAILY_LIMIT_EXCEEDED"


def test_transfer_duplicate_reference_rejected():
    body = {
        "source_account_id": "ACC-1001",
        "destination_account_id": "ACC-CAP",
        "amount": "25.00",
        "currency": "USD",
        "reference_id": "TX-V7",
    }
    first = client.post("/transfer", json=body).json()
    second = client.post("/transfer", json=body).json()
    assert first["action"] == "transfer"
    assert second["reason_code"] == "DUPLICATE_SUBMISSION"


def test_transfer_idempotency_key_replay_does_not_double_move_funds():
    body = {
        "source_account_id": "ACC-1001",
        "destination_account_id": "ACC-CAP",
        "amount": "25.00",
        "currency": "USD",
        "reference_id": "TX-V8",
        "idempotency_key": "TX-IDEMP-1",
    }
    client.post("/transfer", json=body)
    second = client.post("/transfer", json=body).json()
    assert second["idempotent_replay"] is True
    assert _bal("ACC-1001") == Decimal("975.00")  # moved exactly once
    assert _bal("ACC-CAP") == Decimal("10025.00")


# --- audit log content: no unmasked PAN/CVV-shaped pattern, ever -----------

@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN FINDING (2026-07-06, docs/sprint11-test-hardening-plan.md sec2A): "
        "reference_id has no format constraint in mock_api/models.py, and "
        "mock_api/app.py _audit() logs it verbatim with no masking/redaction. "
        "A caller can put a PAN-shaped value in reference_id and it will be "
        "written to the audit log unmasked. Left as a tracked xfail (not "
        "silently fixed) pending a product decision: reject PAN-shaped "
        "reference_id values, or redact PAN-shaped substrings in _audit() "
        "before logging. See PROGRESS.md."
    ),
)
def test_audit_log_never_echoes_a_pan_shaped_reference_id_unmasked(caplog):
    # reference_id is a free-form opaque string per mock_api/models.py — there
    # is no dedicated "card number" field on DebitRequest. This test checks
    # what actually happens if a caller puts a PAN-shaped value into the one
    # unconstrained string field that _audit() logs verbatim, since nothing
    # in the request schema stops that from happening. See PROGRESS.md for
    # what this test found.
    pan_shaped_reference = "4111111111111111"
    with caplog.at_level(logging.INFO, logger="mock_api.audit"):
        client.post(
            "/debit",
            json={
                "account_id": "ACC-1001",
                "amount": "10.00",
                "currency": "USD",
                "reference_id": pan_shaped_reference,
            },
        )
    log_text = caplog.text
    assert pan_shaped_reference not in log_text, (
        "mock_api's audit log echoed a PAN-shaped reference_id verbatim — "
        "reference_id has no format constraint and _audit() does not mask "
        "or reject PAN-shaped values placed in it (see docs/sprint11-test-"
        "hardening-plan.md §2A and PROGRESS.md for the finding)."
    )
