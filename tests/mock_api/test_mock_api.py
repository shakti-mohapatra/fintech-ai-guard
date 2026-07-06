import sys
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
