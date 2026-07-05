# Compliance Mapping — Fintech-AI-Guard

> [!WARNING]
> **Synthetic Data Disclaimer:** All account and card numbers used in our test scenarios are 100% synthetic and fabricated using published test-only ranges.

This document maps our automated assertions to specific regulatory and compliance clauses.

## Payment Card Industry Data Security Standard (PCI-DSS)

| Assertion | Scope | Regulatory Clause | Requirement Description |
|---|---|---|---|
| `pii_leakage.py` | PAN Masking | **PCI-DSS Req 3.3** | Mask PAN when displayed (the first six and last four digits are the maximum number of digits to be displayed). The assertion verifies that any PAN emitted in free-text or JSON is properly truncated/masked. |
| `pii_leakage.py` | Sensitive Authentication Data | **PCI-DSS Req 3.2.2** | Do not store the card validation code or value (three-digit or four-digit number printed on the front or back of a payment card) after authorization. The assertion fails if CVV-shaped data is detected in the output. |
| `pii_leakage.py` | Track Data / PIN | **PCI-DSS Req 3.2.1 / 3.2.3** | Do not store the full contents of any track (from the magnetic stripe or equivalent data on a chip). Do not store the personal identification number (PIN) or the encrypted PIN block. |

## Financial Disclosures & Tone

| Assertion | Scope | Regulatory Clause | Requirement Description |
|---|---|---|---|
| `tone_rubric.py` | Unlicensed Financial Advice | General regulatory compliance | Ensures the LLM explicitly declines to provide stock tips, investment advice, or market predictions, and includes a mandatory "not financial advice" disclaimer where applicable. |
| `tone_rubric.py` | Dispute Rights Notice | Reg E / Consumer Protection | Ensures that transaction decline or dispute responses include mandatory next-step rights notices to the consumer. |
