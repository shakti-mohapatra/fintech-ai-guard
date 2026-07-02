"""In-memory ledger backing the mock API.

Deliberately not a database — this is a deterministic, resettable stub for
tests and red-team probing, not a persistence layer. Everything is stored
in integer minor units (cents). `reset()` restores the seeded synthetic
accounts so each test starts from a known state.

All account/card data here is fabricated. No real PANs, no real account
numbers (see docs/plan.md: synthetic data only, ever).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from threading import Lock


def to_minor_units(amount: Decimal) -> int:
    scaled = amount * 100
    if scaled != scaled.to_integral_value():
        raise ValueError("amount must have at most 2 decimal places")
    return int(scaled)


def to_decimal(minor: int) -> Decimal:
    return (Decimal(minor) / 100).quantize(Decimal("0.01"))


@dataclass
class Account:
    account_id: str
    currency: str
    balance_minor: int
    daily_limit_minor: int
    daily_debited_minor: int = 0


@dataclass
class DebitRecord:
    reference_id: str
    account_id: str
    amount_minor: int
    currency: str
    refunded_minor: int = 0  # cumulative refunds already issued against this debit


@dataclass
class _State:
    accounts: dict[str, Account] = field(default_factory=dict)
    debits: dict[str, DebitRecord] = field(default_factory=dict)  # by reference_id
    seen_references: set[str] = field(default_factory=set)  # every processed reference_id
    idempotency: dict[str, dict] = field(default_factory=dict)  # key -> serialized response


_lock = Lock()
_state = _State()


def _seed() -> _State:
    return _State(
        accounts={
            "ACC-1001": Account("ACC-1001", "USD", balance_minor=100_000, daily_limit_minor=1_000_000),
            "ACC-2002": Account("ACC-2002", "EUR", balance_minor=50_000, daily_limit_minor=500_000),
            "ACC-LOW": Account("ACC-LOW", "USD", balance_minor=1_000, daily_limit_minor=1_000_000),
            "ACC-CAP": Account("ACC-CAP", "USD", balance_minor=1_000_000, daily_limit_minor=250_000),
        }
    )


def reset() -> None:
    """Restore the seeded state. Call from a test fixture before each test."""
    global _state
    with _lock:
        _state = _seed()


def get_lock() -> Lock:
    return _lock


def get_account(account_id: str) -> Account | None:
    return _state.accounts.get(account_id)


def get_debit(reference_id: str) -> DebitRecord | None:
    return _state.debits.get(reference_id)


def reference_seen(reference_id: str) -> bool:
    return reference_id in _state.seen_references


def record_debit(record: DebitRecord) -> None:
    _state.debits[record.reference_id] = record
    _state.seen_references.add(record.reference_id)


def mark_reference_seen(reference_id: str) -> None:
    _state.seen_references.add(reference_id)


def get_idempotent(key: str) -> dict | None:
    return _state.idempotency.get(key)


def store_idempotent(key: str, response: dict) -> None:
    _state.idempotency[key] = response


# Seed on import so the app is usable without an explicit reset().
reset()
