# mock_api

A minimal FastAPI stub whose purpose is to give the evaluation suite a
**real callable target with a real ledger/authorization boundary** — so
business-logic guarantees can be *proven* against a running system, not
just asserted about an LLM's free text. Sprint 8's BFLA/BOLA red-team
plugins also need a target like this (see `docs/plan.md`).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/debit` | Debit an account. Enforces amount validity, daily limit, sufficient funds, duplicate/idempotency safety. |
| `POST` | `/refund` | Refund against a prior debit. Only ever **credits** — structurally cannot debit. |
| `GET` | `/balance/{account_id}` | Read-only balance + daily-usage snapshot (makes debit/refund effects observable in tests). |
| `GET` | `/healthz` | Liveness. |

## Provable properties

- **Refund never debits.** `_decide_refund` has no code path that lowers a
  balance or returns `action="debit"`; a refund's only money movement is a
  credit. `tests/test_mock_api.py` asserts a refund raises the balance and
  records `action="refund"`.
- **Idempotent replay never double-charges.** A repeated `idempotency_key`
  returns the original stored response (`idempotent_replay: true`) without
  re-applying the movement — the network-retry case.
- **Duplicate reference is rejected.** A `reference_id` for an
  already-processed transaction is rejected with `DUPLICATE_SUBMISSION` —
  the double-submit case.
- **Bad amounts / over-limit / currency mismatch / unknown account** are
  rejected with an explicit `reason_code`, never silently processed.
- **Money is integer minor units end to end.** Decimals are parsed via
  `str` and converted to cents on entry; floats never touch a balance.

## Money & data

All amounts are handled in integer minor units (cents). All seeded
accounts and any card/account data are **synthetic** — no real PANs or
account numbers, ever (`docs/plan.md`).

## Running locally

```bash
uvicorn mock_api.app:app --reload
# http://127.0.0.1:8000/docs for the OpenAPI UI
```

## Scope

Minimal by design (Sprint 3). Balance-check expansion and multi-step
transfer flows are Sprint 9; the read-only `/balance` here exists only to
make the debit/refund effects observable for testing.
