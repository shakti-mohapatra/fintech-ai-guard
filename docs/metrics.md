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
