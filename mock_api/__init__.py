"""Minimal FastAPI stub for provable business-logic testing.

Exists so the "a refund must never trigger a debit" story (and, later,
BFLA/BOLA red-team probing in Sprint 8) has a real callable target with a
real authorization/ledger boundary, rather than a plain text model. All
money is handled in integer minor units internally; decision responses
carry an explicit reason_code. See mock_api/README.md.
"""
