# QA Metrics & Methodology — Fintech-AI-Guard

> [!WARNING]
> **Synthetic Data Disclaimer:** All data feeding into these metrics is strictly synthetic test data.

This document outlines how our evaluation metrics are computed and what they represent.

## Cross-Run Consistency Methodology

Because LLMs are non-deterministic by nature, evaluating their reliability requires measuring how consistent they are across multiple executions of the exact same scenario.

1. **Determinism (temp = 0):** 
   - **Method:** We run the same scenario $N$ times at temperature `0.0`.
   - **Metric:** Percentage of runs that yield the exact same character-for-character output.
   - **Goal:** Establish a baseline for how much structural noise the provider's API introduces even at zero temperature.

2. **Semantic Consistency (sampled-N, temp > 0):**
   - **Method:** We run the same scenario $N$ times at a production-representative temperature (e.g., `0.3` or `0.7`).
   - **Metric:** Percentage of runs where the model reaches the *same business-logic decision* (e.g., all 5 runs successfully declined an injection attempt, or all 5 runs returned the correct `reason_code`), regardless of variations in free-text prose.
   - **Goal:** Ensure the model's core decision-making boundary is stable under generation entropy.

## Core Evaluation Metrics

| Metric | Computation | What it catches |
|---|---|---|
| **Composite Compliance Pass Rate** | Total Passed Assertions / Total Scenarios Run | Overall headline number for pipeline readiness. |
| **Hallucination Rate** | Scenarios failing `hallucination_check.py` / Total Hallucination Scenarios | Fabricated financial facts (amounts, dates, entities). |
| **Prompt-Injection Resistance Rate** | Scenarios passing `injection_resistance.py` / Total Injection Scenarios | Direct and document-embedded instruction overrides. |
| **Schema Validation Pass Rate** | Scenarios passing `schema_validator.py` / Total JSON Scenarios | Malformed/non-conforming structured output. |
| **Numeric Precision Error Rate** | Scenarios failing `numeric_precision.py` / Total Precision Scenarios | Float/rounding errors in currency math. |
| **Business-Logic Consistency Rate** | Scenarios passing `logic_consistency.py` / Total Logic Scenarios | Wrong action selected (e.g. refund triggers debit). |
| **Idempotency Handling Rate** | Scenarios passing `idempotency_check.py` / Total Idempotency Scenarios | Duplicate submissions blindly processed. |
| **PII/PCI Leakage Rate** | Scenarios failing `pii_leakage.py` / Total PII Scenarios | Unmasked sensitive data emitted in output. |
| **L3 Extraction Accuracy Rate** | Correctly extracted L3 fields / Total Expected Fields | Errors in line-item/tax extraction. |
| **Tone & Disclosure Compliance Score** | Scenarios passing `tone_rubric.py` / Total Tone Scenarios | Missing mandatory regulatory disclosures. |
| **Authorization-Boundary Integrity** | Sprint 8 redteam BOLA/BFLA pass rate + structural blocks from `redteam_authz` | One account acting on another's data. |

## Meta-QA Test Coverage (framework code, not scenario grading)

Distinct from the LLM-facing QA metrics above — this is line coverage of the
*harness itself* (`assertions/`, `mock_api/`, `scripts/`), via
`pytest --cov=assertions --cov=mock_api --cov=scripts --cov-report=term-missing`
(Sprint 12.1, `docs/sprint11-test-hardening-plan.md`). This is the concrete
artifact behind `CLAUDE.md`'s "~100% test coverage (report)" bar — a number
regenerated from a real run, not a target asserted in prose.

**Last measured (2026-07-06, 389 passed / 50 skipped / 1 xfailed): 89% overall.**

| Module | Coverage | Note |
|---|---|---|
| `assertions/` (all 8 modules + dispatch) | 91-100% each | Uncovered lines are mostly defensive `except` branches not reachable by valid fixtures. |
| `mock_api/app.py` | 100% | Every decision branch (debit/refund/transfer x every reason code) now has a covering test after Sprint 12.3's section 2A additions. |
| `mock_api/ledger.py`, `mock_api/models.py` | 99% each | One defensive line each (`_coerce_decimal`'s `except`, one Account dataclass default path). |
| `scripts/redteam_authz.py`, `scripts/generate_report.py`, `scripts/run_eval.py` | 96-100% | Well-covered by existing Sprint 8/5 tests. |
| `scripts/agent_target.py` | 67% | Uncovered branches are the real-Gemini-call and retry/backoff paths, only exercisable via `PROMPTFOO_REDTEAM_DRY_RUN=1` or a live run (Sprint 13) — expected, not a gap to close with more unit tests. |
| `scripts/generate_redteam_report.py` | 71% | Uncovered branches parse promptfoo redteam's live JSON output shape, not yet exercised against a real run (Sprint 13). |
| `scripts/dashboard.py` | 0% | Streamlit UI script — not unit-testable in the traditional sense; out of scope for this coverage pass (would need a Streamlit test harness, not requested). |

Coverage is a diagnostic, not a gate — 100% is the ceiling this project's own
"Fiverr-ready bar" describes, not a hard requirement (`CLAUDE.md`). The three
sub-100% areas above (`agent_target.py`, `generate_redteam_report.py`,
`dashboard.py`) are each explained by what they're waiting on (a live run,
or being genuinely out of unit-test scope), not by missing test-writing
effort.
