"""FastAPI app exposing POST /debit and POST /refund.

Design intent is that the business-logic guarantees are *provable*, not
just asserted in prose:

  * A refund only ever credits a balance and returns action="refund".
    There is no code path in `refund()` that debits — the "refund must
    never trigger a debit" property holds structurally, not by luck.
  * A replayed idempotency key returns the original stored response and
    never re-applies the money movement (network-retry safety).
  * A resubmitted reference_id for an already-processed transaction is
    rejected as a duplicate (double-submit safety).
  * Zero/negative amounts, over-limit debits, currency mismatches, and
    unknown accounts are rejected with an explicit machine-readable
    reason_code rather than silently processed.

Every decision is emitted to the `mock_api.audit` logger as a structured
JSON line (reason code included), which is the audit-trail hook the plan
calls for.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from fastapi import FastAPI, HTTPException

from . import ledger
from .ledger import DebitRecord, TransferRecord, to_decimal, to_minor_units
from .models import (
    Action,
    BalanceResponse,
    DebitRequest,
    ReasonCode,
    RefundRequest,
    TransferRequest,
    TransactionResponse,
)

logger = logging.getLogger("mock_api.audit")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

app = FastAPI(title="Fintech-AI-Guard Mock API", version="0.1.0")


def _audit(endpoint: str, request_ref: str, response: TransactionResponse) -> None:
    logger.info(
        json.dumps(
            {
                "endpoint": endpoint,
                "reference_id": request_ref,
                "account_id": response.account_id,
                "action": response.action.value,
                "reason_code": response.reason_code.value,
                "amount": str(response.amount),
                "currency": response.currency,
                "idempotent_replay": response.idempotent_replay,
            }
        )
    )


def _replay(idempotency_key: str | None) -> TransactionResponse | None:
    if not idempotency_key:
        return None
    stored = ledger.get_idempotent(idempotency_key)
    if stored is None:
        return None
    response = TransactionResponse(**stored)
    response.idempotent_replay = True
    return response


def _remember(idempotency_key: str | None, response: TransactionResponse) -> None:
    if idempotency_key:
        ledger.store_idempotent(idempotency_key, response.model_dump(mode="json"))


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/balance/{account_id}", response_model=BalanceResponse)
def balance(account_id: str) -> BalanceResponse:
    account = ledger.get_account(account_id)
    if account is None:
        # Read-only lookup; 404 is the honest answer for an unknown resource.
        raise HTTPException(status_code=404, detail="unknown account")
    return BalanceResponse(
        account_id=account.account_id,
        currency=account.currency,
        balance=to_decimal(account.balance_minor),
        daily_debited=to_decimal(account.daily_debited_minor),
        daily_limit=to_decimal(account.daily_limit_minor),
    )


@app.post("/debit", response_model=TransactionResponse)
def debit(req: DebitRequest) -> TransactionResponse:
    replay = _replay(req.idempotency_key)
    if replay is not None:
        _audit("debit", req.reference_id, replay)
        return replay

    with ledger.get_lock():
        response = _decide_debit(req)
        _remember(req.idempotency_key, response)

    _audit("debit", req.reference_id, response)
    return response


@app.post("/refund", response_model=TransactionResponse)
def refund(req: RefundRequest) -> TransactionResponse:
    replay = _replay(req.idempotency_key)
    if replay is not None:
        _audit("refund", req.reference_id, replay)
        return replay

    with ledger.get_lock():
        response = _decide_refund(req)
        _remember(req.idempotency_key, response)

    _audit("refund", req.reference_id, response)
    return response


@app.post("/transfer", response_model=TransactionResponse)
def transfer(req: TransferRequest) -> TransactionResponse:
    replay = _replay(req.idempotency_key)
    if replay is not None:
        _audit("transfer", req.reference_id, replay)
        return replay

    with ledger.get_lock():
        response = _decide_transfer(req)
        _remember(req.idempotency_key, response)

    _audit("transfer", req.reference_id, response)
    return response


def _reject(req, reason: ReasonCode, *, balance_minor: int | None = None) -> TransactionResponse:
    return TransactionResponse(
        action=Action.reject,
        amount=req.amount,
        currency=req.currency,
        reason_code=reason,
        reference_id=req.reference_id,
        account_id=req.account_id,
        resulting_balance=to_decimal(balance_minor) if balance_minor is not None else None,
    )


def _decide_debit(req: DebitRequest) -> TransactionResponse:
    account = ledger.get_account(req.account_id)
    if account is None:
        return _reject(req, ReasonCode.unknown_account)

    if req.currency != account.currency:
        return _reject(req, ReasonCode.currency_mismatch, balance_minor=account.balance_minor)

    amount_minor = to_minor_units(req.amount)
    if amount_minor <= 0:
        return _reject(req, ReasonCode.invalid_amount, balance_minor=account.balance_minor)

    if ledger.reference_seen(req.reference_id):
        return _reject(req, ReasonCode.duplicate_submission, balance_minor=account.balance_minor)

    if account.daily_debited_minor + amount_minor > account.daily_limit_minor:
        return _reject(req, ReasonCode.daily_limit_exceeded, balance_minor=account.balance_minor)

    if amount_minor > account.balance_minor:
        return _reject(req, ReasonCode.insufficient_funds, balance_minor=account.balance_minor)

    account.balance_minor -= amount_minor
    account.daily_debited_minor += amount_minor
    ledger.record_debit(
        DebitRecord(
            reference_id=req.reference_id,
            account_id=req.account_id,
            amount_minor=amount_minor,
            currency=req.currency,
        )
    )
    return TransactionResponse(
        action=Action.debit,
        amount=req.amount,
        currency=req.currency,
        reason_code=ReasonCode.approved,
        reference_id=req.reference_id,
        account_id=req.account_id,
        resulting_balance=to_decimal(account.balance_minor),
    )


def _decide_refund(req: RefundRequest) -> TransactionResponse:
    account = ledger.get_account(req.account_id)
    if account is None:
        return _reject(req, ReasonCode.unknown_account)

    original = ledger.get_debit(req.original_reference_id)
    if original is None or original.account_id != req.account_id:
        return _reject(req, ReasonCode.no_original_transaction, balance_minor=account.balance_minor)

    if req.currency != account.currency or req.currency != original.currency:
        return _reject(req, ReasonCode.currency_mismatch, balance_minor=account.balance_minor)

    amount_minor = to_minor_units(req.amount)
    if amount_minor <= 0:
        return _reject(req, ReasonCode.invalid_amount, balance_minor=account.balance_minor)

    if ledger.reference_seen(req.reference_id):
        return _reject(req, ReasonCode.duplicate_submission, balance_minor=account.balance_minor)

    if original.refunded_minor + amount_minor > original.amount_minor:
        return _reject(req, ReasonCode.refund_exceeds_original, balance_minor=account.balance_minor)

    # The only money movement a refund can make: a credit. No debit path.
    account.balance_minor += amount_minor
    original.refunded_minor += amount_minor
    ledger.mark_reference_seen(req.reference_id)
    return TransactionResponse(
        action=Action.refund,
        amount=req.amount,
        currency=req.currency,
        reason_code=ReasonCode.customer_request,
        reference_id=req.reference_id,
        account_id=req.account_id,
        resulting_balance=to_decimal(account.balance_minor),
    )


def _reject_transfer(req: TransferRequest, reason: ReasonCode, *, balance_minor: int | None = None) -> TransactionResponse:
    return TransactionResponse(
        action=Action.reject,
        amount=req.amount,
        currency=req.currency,
        reason_code=reason,
        reference_id=req.reference_id,
        account_id=req.source_account_id,
        resulting_balance=to_decimal(balance_minor) if balance_minor is not None else None,
    )


def _decide_transfer(req: TransferRequest) -> TransactionResponse:
    if req.source_account_id == req.destination_account_id:
        return _reject_transfer(req, ReasonCode.same_account_transfer)

    source = ledger.get_account(req.source_account_id)
    dest = ledger.get_account(req.destination_account_id)
    
    if source is None or dest is None:
        return _reject_transfer(req, ReasonCode.unknown_account)

    if req.currency != source.currency or req.currency != dest.currency:
        return _reject_transfer(req, ReasonCode.currency_mismatch, balance_minor=source.balance_minor)

    amount_minor = to_minor_units(req.amount)
    if amount_minor <= 0:
        return _reject_transfer(req, ReasonCode.invalid_amount, balance_minor=source.balance_minor)

    if ledger.reference_seen(req.reference_id):
        return _reject_transfer(req, ReasonCode.duplicate_submission, balance_minor=source.balance_minor)

    if source.daily_debited_minor + amount_minor > source.daily_limit_minor:
        return _reject_transfer(req, ReasonCode.daily_limit_exceeded, balance_minor=source.balance_minor)

    if amount_minor > source.balance_minor:
        return _reject_transfer(req, ReasonCode.insufficient_funds, balance_minor=source.balance_minor)

    source.balance_minor -= amount_minor
    source.daily_debited_minor += amount_minor
    dest.balance_minor += amount_minor
    
    ledger.record_transfer(
        TransferRecord(
            reference_id=req.reference_id,
            source_account_id=req.source_account_id,
            destination_account_id=req.destination_account_id,
            amount_minor=amount_minor,
            currency=req.currency,
        )
    )
    return TransactionResponse(
        action=Action.transfer,
        amount=req.amount,
        currency=req.currency,
        reason_code=ReasonCode.approved,
        reference_id=req.reference_id,
        account_id=req.source_account_id,
        resulting_balance=to_decimal(source.balance_minor),
    )
