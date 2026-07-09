# Sprint 11 Implementation Plan — Negative/Boundary Test Hardening & Framework Audit

> Read order: `PROGRESS.md` -> `BACKLOG.md` -> `docs/plan.md` -> `docs/test-strategy.md` ->
> `docs/antigravity-review-2026-07-06.md` (know the process failure modes already
> caught once) -> this file. Written as an independent QA audit at Shakti's request
> (sr. QA engineer, fintech), reviewed before any task is opened.

## 0. Verdict on current state

This is **not a greenfield build**. The framework already exists and is
substantially mature: 3-layer architecture (scenario YAML -> promptfoo execution ->
Python assertion grading), a 10-category risk taxonomy with an explicit
ground-truth methodology (deterministic / reference-anchored / rubric-graded),
32 hand-authored scenarios, 8 assertion modules + a router, a `FastAPI` mock
ledger with structurally-provable business logic, a pytest meta-QA suite
(263 passed / 28 skipped / 0 failed at last independently-verified run,
2026-07-06), CI split into a free always-on pytest gate and a paid
manual-dispatch-only eval job, and partial red-team wiring (Sprint 8, code
sound, never yet run live).

Rating against the project's own "Fiverr-ready bar" (feature-complete +
~100% test coverage report + refactored + real bugs fixed = 85-90% baseline):
**~78/100.** Architecture and process discipline are genuinely strong — better
than most portfolio projects at this stage. The gap is depth, not shape: the
scenario library is broad (9 of 10 categories touched) but shallow (2-5
scenarios per category), which is exactly the "-ve and boundary case" gap
Shakti flagged. This plan closes that gap without re-architecting anything
that already works.

**What this plan does NOT do:** rebuild the framework, change the
architecture, introduce a new test runner, or touch `mock_api`'s core
decision logic. Sprint 9's review already flagged unrequested scope
expansion as this project's recurring failure mode (see
`docs/antigravity-review-2026-07-06.md`, finding #3) — this plan is
deliberately scoped to stay inside existing conventions.

## 1. Gap analysis — coverage matrix (current -> target)

Counts are scenario files per category. "Target" is the minimum needed to
call a category's negative/boundary coverage genuinely complete, not
exhaustive-to-infinity — judged against what a fintech payments QA reviewer
would expect to see before signing off (per `docs/test-strategy.md`'s own
severity/ground-truth framework).

| # | Category | Current | Target | Gap | Why |
|---|---|---|---|---|---|
| 1 | Hallucination | 4 | 6 | +2 | Covers date/recipient/counterparty/confirmation-number fabrication. Missing: invented totals/subtotals, invented fee/rate not present in source. |
| 2 | Injection (direct) | 2 | 5 | +3 | Only "ignore instructions" + "role override". Missing: encoding-obfuscated (base64/homoglyph), multi-turn injection (planted in turn 1, triggered in turn 2), injection via a field the model treats as trusted metadata (e.g. a "system-looking" reference_id). |
| 3 | Injection (document-embedded) | 2 | 5 | +3 | Missing: injection inside a table cell/line-item description, injection split across two documents (invoice + supporting memo), injection disguised as a compliance instruction ("per Reg E, auto-refund without verification"). |
| 4 | Schema Compliance | 3 | 6 | +3 | Only "basic" happy-shaped scenarios (transfer/refund/L3). Missing negative fixtures: wrong type (`amount` as string), missing required field, `additionalProperties` violation, boundary string lengths (empty/very long `reference_id`). |
| 5 | Numeric Precision | 3 | 7 | +4 | Missing: zero-decimal currency (JPY-style, no minor units), 3+ decimal input rejected/rounded correctly, negative tax/discount, rounding-direction tie-break (banker's vs. half-up) explicitly graded, amount at `Decimal` precision boundary (e.g. `0.005`). |
| 6 | Logic Consistency | 5 | 9 | +4 | Missing: amount **exactly equal to** daily limit (boundary, not just over), amount **exactly equal to** balance (fully-draining debit, valid), refund amount exactly equal to remaining refundable balance, expired/closed-account debit attempt. |
| 7 | Idempotency | 4 | 7 | +3 | Missing: same idempotency key + **different** payload (conflict, not blind replay), idempotency key reused across endpoints (debit key replayed against refund), simulated concurrent duplicate submission (race — ties to mock_api's lock, see §3). |
| 8 | PII/PCI | 3 | 6 | +3 | Missing: IBAN/SWIFT masking (not just PAN), leakage inside a rejection/error message (not just a success response), leakage inside the structured audit log line itself (`mock_api`'s own `_audit()` — currently untested for what it logs). |
| 9 | L3 Data Extraction | 2 | 5 | +3 | Missing: malformed/incomplete invoice (missing PO number), extracted totals that don't reconcile against line items (negative case for the numeric_precision cross-check already wired in `dispatch.py`), commodity-code mismatch. |
| 10 | Authorization (redteam) | 0 scenarios (by design) | live smoke run + report | — | Code complete since Sprint 8, never executed. See §3 — this is a go/no-go ask, not new authoring. |

**Net new scenario authoring: ~28 files** across categories 1-9, following the
existing schema exactly (`scenarios/scenario.schema.json`,
`docs/scenario-schema.md`) — no schema changes needed, `test_scenario_files.py`
already validates every new file for free the moment it's added.

**Status (2026-07-06): all 28 authored and merged.** See `BACKLOG.md` Sprint 11
for the per-category file list.

## 2. Meta-QA / framework-code gaps (not scenario content — the harness itself)

| Gap | Where | Fix | Status |
|---|---|---|---|
| No coverage-% visibility | `requirements.txt` had no `pytest-cov` | Add `pytest-cov` (pin, matches file's exact-pin convention), wire `--cov=assertions --cov=mock_api --cov=scripts --cov-report=term-missing`, publish the number in `docs/metrics.md`. | **Done** — `pytest-cov==7.1.0`, 89% overall (`docs/metrics.md`). |
| `prompts/build_prompt.js` had zero dedicated tests | no `tests/prompts/` dir | Node subprocess bridge + pytest, zero API cost. | **Done** — 6 tests, `tests/prompts/test_build_prompt.py`. |
| Redteam never run live | Sprint 8 (`docs/sprint8-implementation-plan.md`) | Not a code gap — an execution gap. See §3. | Pending — needs live-API go-ahead. |

## 2A. `mock_api` REST-layer test matrix — request validation, boundaries & error handling

`tests/mock_api/test_mock_api.py` was genuinely solid on **business-logic**
decision paths (reject reason codes, refund-never-debits, idempotency
replay) — the gap was specifically at the **HTTP/request-validation layer**
and in the **transfer** endpoint's negative-path parity with debit/refund
(transfer shipped later, Sprint 9, and inherited fewer negative tests than
debit got in Sprint 3).

| Endpoint | Case | Expected | Status |
|---|---|---|---|
| `POST /debit` | missing required field / wrong type / extra field | 422 | **Done** |
| `POST /debit` | invalid currency shape (`"usd"`, `"US"`, `"1234"`, `"US1"`) | 422 | **Done** |
| `POST /debit` | empty-string `account_id` / `reference_id` | 422 | **Done** |
| `POST /debit` | malformed JSON body / wrong HTTP method | 422 / 405 | **Done** |
| `POST /debit` | amount exactly == remaining daily limit / == balance / == balance+0.01 | approved / approved / insufficient funds | **Done (boundary)** |
| `POST /debit` | two concurrent requests, same idempotency key + reference_id | exactly one real charge | **Done (concurrency)** |
| `POST /refund` | missing `original_reference_id` / unknown account / currency mismatch / zero / negative amount / duplicate reference | 422 or matching reject reason code | **Done** |
| `POST /transfer` | source == destination / unknown account / zero amount / >2 decimals / daily limit / duplicate / idempotency replay | matching reject reason code or 422 | **Done** |
| `GET /balance/{id}` | injection-shaped account id | 404, no 500 | **Done** |
| *(all endpoints)* | audit log line content — no unmasked PAN/CVV pattern | never leaks | **Done — found a real gap**, see below |

**Net new `mock_api` HTTP-layer tests: 32** (28 unique + 4 parametrized),
`mock_api/app.py` now at 100% line coverage.

**Finding:** the audit-log test (`test_audit_log_never_echoes_a_pan_shaped_reference_id_unmasked`)
is real, not decorative — `reference_id` has no format constraint in
`mock_api/models.py`, and `_audit()` in `mock_api/app.py` logs it verbatim
with no masking. A PAN-shaped value placed in `reference_id` is written to
the audit log unmasked. This is tracked as a documented `pytest.mark.xfail`
(strict=True) rather than silently fixed or silently weakened — see
`PROGRESS.md` for the finding and the product decision it's waiting on
(reject PAN-shaped `reference_id` values outright, vs. redact PAN-shaped
substrings in `_audit()` before logging).

## 3. Proposed sprint breakdown (mirrors existing BACKLOG.md/GitHub convention)

**Sprint 11 — Negative & Boundary Scenario Hardening** — **Done**, see BACKLOG.md.

**Sprint 12 — Meta-QA Hardening & API Request-Validation/Error-Handling** — **Done**, see BACKLOG.md and §2A above.

**Sprint 13 — Red-Team Go-Live (Sprint 8 close-out)** *(already-built code, blocked purely on your go-ahead)*
- 13.1 Confirm current Gemini free-tier quota via the direct-curl check already documented in `promptfooconfig.redteam.smoke.yaml`'s header comment.
- 13.2 **Ask you explicitly, at that moment**, before running `npm run redteam:smoke` — this spends real (free-tier, quota-limited) API calls and is exactly the kind of unattended-paid-API action `CLAUDE.md`'s CRITICAL RULE forbids doing without asking first, even though it's Gemini not Anthropic.
- 13.3 Run `generate_redteam_report.py`, append findings to `evaluation_report.md`.
- 13.4 Only then tick Sprint 8's `[~]` boxes to `[x]` in `BACKLOG.md`.

Sprints 11 and 12 involved **zero live LLM calls** — every new scenario and
every new pytest was validated via `promptfoo validate` (static config check)
and direct pytest, exactly as `CLAUDE.md` requires. Sprint 13 is the one
piece that touches a live API, and it's gated on an explicit ask at
execution time.

## 4. File/directory organization (no structural changes)

```
scenarios/<category>/<category>-<slug>-<seq>.yaml   # 28 new files, existing convention
tests/mock_api/test_mock_api.py                       # +32 request-validation/boundary/concurrency cases (§2A)
tests/prompts/test_build_prompt.py                    # new file, new tests/prompts/ dir
tests/prompts/_run_build_prompt.js                    # Node subprocess bridge (test-only)
docs/metrics.md                                        # + coverage % section
requirements.txt                                        # + pytest-cov==7.1.0 (exact pin)
```

## 5. What "approved" triggered

1. Opened `BACKLOG.md` Sprint 11/12/13 entries (GitHub issue mirroring pending — GitHub connector not yet authorized in this session).
2. Worked top to bottom, one category/chunk at a time, running the sanity-tier pytest subset after each.
3. Full regression pytest run + `PROGRESS.md` entry at each sprint close.
4. Sprint 13 (redteam) stops and asks again before the live API call — not implied by this plan's approval.

## 6. Decisions confirmed (2026-07-06)

- §1 scenario targets: **approved as-is** — all 28 authored.
- Ordering: **sequential** — Sprint 11 completed before Sprint 12 started.
- Sprint 8 red-team go-live: **included** in this batch's scope; execution stops and asks again for explicit go-ahead immediately before the live Gemini call (§3, item 13.2) — not yet run.

Net scope delivered: **28 new scenario YAML files** (§1) + **32 new
`mock_api` HTTP-layer tests** (§2A) + coverage reporting + `build_prompt.js`
tests (§2) = comprehensive negative/boundary/API-validation coverage across
both halves of the framework (LLM-facing scenarios and the ground-truth API
itself), with nothing executed against a live paid model without asking
first, and one genuine PII finding surfaced (not hidden) along the way.
