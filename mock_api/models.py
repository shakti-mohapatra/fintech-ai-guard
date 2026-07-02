"""Request/response models and the reason-code vocabulary for the mock API.

Money crosses the wire as a decimal `amount` + ISO-4217 `currency`, but is
converted to integer minor units (cents) the moment it enters the ledger —
floats never touch balances. Response shape is intentionally a superset of
scenarios/schema/transaction_action.schema.json (action + reason_code), so
the same decision vocabulary the LLM scenarios grade against is what the
ground-truth API actually emits.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Action(str, Enum):
    debit = "debit"
    refund = "refund"
    hold = "hold"
    reject = "reject"


class ReasonCode(str, Enum):
    approved = "APPROVED"
    invalid_amount = "INVALID_AMOUNT"
    daily_limit_exceeded = "DAILY_LIMIT_EXCEEDED"
    insufficient_funds = "INSUFFICIENT_FUNDS"
    duplicate_submission = "DUPLICATE_SUBMISSION"
    idempotent_replay = "IDEMPOTENT_REPLAY"
    unknown_account = "UNKNOWN_ACCOUNT"
    currency_mismatch = "CURRENCY_MISMATCH"
    no_original_transaction = "NO_ORIGINAL_TRANSACTION"
    refund_exceeds_original = "REFUND_EXCEEDS_ORIGINAL"
    customer_request = "CUSTOMER_REQUEST"


def _coerce_decimal(value: object) -> Decimal:
    # Parse through str so a JSON float like 250.50 can't smuggle in binary
    # float error (Decimal(0.1) != Decimal("0.1")).
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"amount is not a valid decimal: {value!r}") from exc


class _TransactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1)
    amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    reference_id: str = Field(min_length=1)
    idempotency_key: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def _parse_amount(cls, value: object) -> Decimal:
        return _coerce_decimal(value)

    @field_validator("amount")
    @classmethod
    def _max_two_decimals(cls, value: Decimal) -> Decimal:
        if (value * 100) != (value * 100).to_integral_value():
            raise ValueError("amount must have at most 2 decimal places")
        return value


class DebitRequest(_TransactionRequest):
    pass


class RefundRequest(_TransactionRequest):
    # A refund must always name the debit it reverses; there is no such thing
    # as an origin-less refund in this ledger.
    original_reference_id: str = Field(min_length=1)


class TransactionResponse(BaseModel):
    action: Action
    amount: Decimal
    currency: str
    reason_code: ReasonCode
    reference_id: str
    account_id: str
    resulting_balance: Decimal | None = None
    idempotent_replay: bool = False


class BalanceResponse(BaseModel):
    account_id: str
    currency: str
    balance: Decimal
    daily_debited: Decimal
    daily_limit: Decimal
