# Progress Log — Fintech-AI-Guard

A running log so multi-day work is easy to pick back up. Newest entry on top.

## 2026-07-03 — Sprint 5 (partial): reporting scripts

**Latest commit:** pending (this entry). Issues #26, #27 closed. Issue #28
left **open** — genuinely blocked on quota, not on missing code; see the
comment left on it. Sprint 5 milestone: 2 of 3 tasks done.

### What shipped

| What | Detail |
|------|--------|
| `scripts/generate_report.py` | Parses a promptfoo JSON export (`results.stats` + per-result `vars`/`failureReason`/`latencyMs`), buckets every result by scenario `category` into the `docs/plan.md` QA Metrics table, computes p50/p95 latency, and lists the metrics it *can't* compute yet (Authorization-Boundary Integrity, Explainability/Reason-Code Completeness, Cross-Run Consistency, cross-category False-Refusal rollup) with a stated reason rather than a placeholder number — required by `docs/plan.md`'s own verification checklist ("real numbers, not placeholders"). Writes a timestamped snapshot into `reports/` and refreshes `evaluation_report.md` |
| `scripts/run_eval.py` | Thin wrapper: `promptfoo eval` → raw JSON to `reports/raw/` (new, gitignored — regenerable, not the curated record) → hands off to `generate_report.py`. Passes extra CLI args straight through (e.g. `--filter-first-n` to cap request count against quota). Propagates promptfoo's own exit code so it still works as a gate on top of the native `PROMPTFOO_PASS_RATE_THRESHOLD` |
| `tests/test_generate_report.py`, `tests/test_run_eval.py` | 12 + 6 pytest cases |

### Design decision worth flagging: error vs. failure, confirmed not guessed

`generate_report.py` needed to know whether a per-result JSON field
reliably distinguishes an assertion *failure* from a transport *error* —
conflating them would misattribute a transient provider 503 as a
model-quality finding, exactly the trap Sprint 4's verification entry
called out at the aggregate level. Rather than guess at the field
semantics, grepped the **installed** `promptfoo` package's own compiled
source (`node_modules/promptfoo/dist/src/tables-*.cjs`) and confirmed
`ResultFailureReason = { NONE: 0, ASSERT: 1, ERROR: 2 }` — that's the
exact per-result enum the report script buckets on. Verified the whole
pipeline against a real (if trivial) promptfoo JSON export from the
`echo`-provider smoke config, not just synthetic pytest fixtures — that
throwaway snapshot was deleted afterward rather than left committed as if
it were real project data (no categories in the smoke config → every row
would've read "not run", which is correct for that config but misleading
sitting in `reports/` next to real curated runs later).

### Why issue #28 is still open

The scenario library is now 32 files (28 + Sprint 3 close-out's 4
tone-disclosure). `gemini-2.5-flash`'s free tier caps at 20 requests/day
— **a single full run no longer fits in one day's budget**, and
tone-disclosure scenarios each add a second call to the
`gemini-2.5-flash-lite` grader bucket. User has said no billing for now.
Left a comment on #28 laying out three options (multi-day split run,
smaller curated subset first, enable billing later) rather than picking
one unprompted — this is a scope/cost call, not a technical one.

**Next:** either the user picks a path for #28, or work moves to Sprint 6
(CI/CD) in parallel — `.github/workflows/eval.yml` and secrets wiring
don't themselves require spending quota to build, only to actually run in
CI, which hits the identical quota question. Worth surfacing before
starting Sprint 6 rather than discovering it mid-sprint.

## 2026-07-03 — Sprint 3 close-out: tone/disclosure + pytest completeness ✅

**Latest commit:** pending (this entry). Issues #20, #22 closed. Sprint 3
milestone closed (0 open / 11 closed) — Sprint 3 is now fully done.

### Grader-model decision (checked in with the user first)

`tone_rubric.py` needs an LLM-judge — no deterministic check for tone is
possible (`docs/test-strategy.md` category 9). Checked in on two things
before authoring: which model grades, and how far to push a live run
today given the standing quota constraint (PROGRESS.md Sprint 4 finding
7). Decisions:
- **Grader defaults to `gemini-2.5-flash-lite`**, not `gemini-2.5-flash`
  (the pinned generation provider in `promptfooconfig.js`) — a separate
  free-tier quota bucket, so grading a tone scenario doesn't compete with
  the generation run for the same 20/day flash budget. Override via a new
  `TONE_GRADER_MODEL` env var (documented in `.env.example`) if a
  different grader is ever wanted; still requires `GOOGLE_API_KEY`
  regardless of which model is named, since the grader call goes straight
  to the Gemini API.
- **User: "make sure it's free, I am not paying extra right now."** No
  billing-requiring model is used anywhere in this change.
- **Today's live-run scope: unit-tests only, no live grader call.** All
  11 new pytest cases mock `tone_rubric._call_grader` — zero API calls,
  zero quota spent. The judge itself will get its first live exercise at
  the next quota window or Sprint 5 snapshot, not today.

### What shipped

| What | Detail |
|------|--------|
| `assertions/tone_rubric.py` | LLM-judge assertion. Grades `output` against the scenario's own `expected_behavior` (required by the schema to be phrased as explicit grading criteria, not narrative). Per `docs/test-strategy.md`'s "reach for deterministic first" rule, an optional `forbidden_patterns` fast-fail runs **before** the LLM call — a scenario with an obvious regex-catchable violation doesn't spend a grader-quota request confirming what a regex already caught. Grader call isolated in `_call_grader()`, a thin `httpx` wrapper around the Gemini `generateContent` endpoint (no new dependency — `httpx` was already in `requirements.txt`), so tests can monkeypatch it cleanly |
| `scenarios/tone-disclosure/*.yaml` (4 files) | Missing not-financial-advice disclaimer (medium); direct pressure for a named-stock buy/sell call, must decline outright (high, also demonstrates the `forbidden_patterns` fast-fail path); unprofessional/defensive response to a hostile customer message (medium); transaction-decline notice missing a dispute-rights next step (medium). `regulatory_ref` left `null` on all four — unlike PII/PCI's PCI-DSS citations, no specific clause was confirmed for this category this session, so nothing was invented; worth a real compliance-citation pass in Sprint 7 (`docs/compliance-mapping.md`) rather than guessed now |
| `assertions/dispatch.py` | `"tone-disclosure": "tone_rubric"` wired into `_CATEGORY_MODULE` |
| `tests/test_tone_rubric.py` | 11 new cases — grader pass/fail, missing `expected_behavior`, the `forbidden_patterns` fast-fail (asserts the grader was **not** called), fenced/non-JSON/malformed grader responses, grader exception handling, default-model and `TONE_GRADER_MODEL`-override behavior, and the missing-`GOOGLE_API_KEY` error path. All mock `_call_grader` — no network, no quota |
| `tests/test_dispatch.py` | Replaced the now-stale "tone-disclosure has no assertion yet" test with a real routing test (mocked grader) |
| `.env.example` | Documented `TONE_GRADER_MODEL` (optional, defaults to `gemini-2.5-flash-lite`) |

### Issue #22 (pytest completeness) — closed alongside #20

Every module in `assertions/` now has a dedicated test file:
`hallucination_check`, `injection_resistance`, `logic_consistency`,
`numeric_precision`, `pii_leakage`, `idempotency_check`, `schema_validator`
(`test_assertions.py`), `dispatch`, `_json_utils`, and now `tone_rubric`.
This was effectively done already per Sprint 4's entry; `tone_rubric.py`
was the one gap, now closed.

### Verification
- `pytest tests/ -v` → **230 passed, 28 skipped** (up from 206/24 in
  Sprint 4; the 4 new skips are `test_injection_subcategory_matches_subdirectory`
  correctly no-op'ing on the 4 new tone-disclosure scenario files) ✓
- `npm run eval:smoke` → 1/1 passed — re-run because `assertions/dispatch.py`
  changed, per the standing "smoke after any config/env change" tier ✓
- Live grader call: **not run today**, by design (see decision above).

### Next: Sprint 5, with a quota gate already visible

The scenario library is now 32 files (28 + 4 tone-disclosure). Sprint 4's
finding 7 flagged that `gemini-2.5-flash`'s free tier caps at 20
requests/day — **a full 32-scenario run already doesn't fit in one day's
budget**, before Sprint 5 or 6 add anything. Sprint 5's "snapshot the
first curated run" task is blocked on this, not on missing code; the two
sub-tasks that are pure code (`scripts/generate_report.py`,
`scripts/run_eval.py`) don't need a live call to build or unit-test, so
those go first. The user has said no billing for now, so live snapshotting
will need either a multi-day split run or accepting a smaller curated
subset — a decision to check in on when the reporting scripts are ready
and there's an actual run to snapshot.

## 2026-07-03 — Sprint 4: promptfoo Wiring ✅

**Latest commit:** pending (this entry). Issues #23, #24, #25 closed. Sprint 4 milestone closed (0 open / 3 closed).

A Google AI Studio key (`GOOGLE_API_KEY`) was added this session — the
first real provider key the project has had. That unblocked live
verification, which is the whole point of this entry: **every finding
below was caught by actually running the eval against a real model, not
by code review.** None of these would have surfaced from the Sprint 0
`echo`-provider smoke test alone, which is exactly why issue #25 existed.

### What shipped

| What | Detail |
|------|--------|
| `assertions/dispatch.py` | Routes each scenario to its category's assertion module via `context.vars.category` — wired once via `defaultTest.assert`, not per-scenario, per the Sprint 2 design decision. `l3-data-extraction` layers `numeric_precision` on top of `schema_validator` when numeric context keys are present. 14 pytest cases, including a regression guard that loads a real scenario file from disk rather than a hand-rolled fixture |
| `promptfooconfig.js` | JS, not YAML — `providers` is built conditionally from whichever of `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`GOOGLE_API_KEY` are actually present, throwing a clear error only if none are. This is the real mechanism behind `docs/plan.md`'s "degrading gracefully" promise; a static YAML list can't omit an entry based on an env var |
| `prompts/build_prompt.js` | Dynamic prompt, category-conditional: the 5 JSON-output categories get the actual target JSON Schema embedded verbatim plus a "respond with ONLY JSON" instruction; the 4 free-text categories get a lighter "this is synthetic test data, don't decline" framing |
| `assertions/_json_utils.py` | `strip_markdown_fences()`, applied in all 4 JSON-parsing assertions (`schema_validator`, `numeric_precision`, `logic_consistency`, `idempotency_check`) |

### Bugs found and fixed by actually running the eval

1. **`schema_validator.py` read `schema_file` from the wrong place.** It read `vars.schema_file` (flat), but every real scenario file — and the canonical schema itself — nests it under `vars.context.schema_file`. This affected 8 scenario files across schema-compliance, logic-consistency, idempotency, and L3-extraction; every one of them would have silently failed with "missing schema_file" the first time `promptfoo eval` ran for real. Fixed with a documented fallback lookup (checks `context.schema_file` first, falls back to flat `schema_file`) so the Sprint 0 smoke test keeps working unchanged. Caught before ever calling a real provider, by rewriting `tests/test_dispatch.py`'s fixtures to mirror the real nested shape instead of a simplified flat one — the simplification is what let the original bug ship unnoticed.
2. **Array-valued vars were silently multiplying test cases.** `required_fields`/`forbidden_patterns` are YAML arrays; promptfoo's default behavior cartesian-expands any array-valued var into one test case per array element. A single scenario with a 3-item `required_fields` silently became 3 test cases (confirmed live: `--filter-first-n 1` ran 3, not 1). Fixed with `defaultTest.options.disableVarExpansion: true`. Left unfixed, this would have 2-5x'd the real cost/quota consumption of every eval run without anyone noticing from the summary numbers alone.
3. **A bare `{{input}}` prompt doesn't work against a real model.** Gemini flatly refused a bare transfer instruction ("I cannot directly transfer money..."), which the `echo` provider's smoke test could never have revealed since `echo` just parrots the input back regardless of framing. Fixed with `prompts/build_prompt.js`'s category-conditional framing.
4. **Telling a model "respond in JSON" isn't enough — it needs the schema.** Once told to emit JSON without seeing the schema, Gemini invented plausible-but-wrong field names (`to_account`, `transaction_type` instead of `recipient_account`) and returned `amount` as a string. This wasn't a model-quality finding — every JSON-category scenario would fail this way regardless of model, since none of them were ever shown the actual contract. Fixed by embedding the real JSON Schema in the prompt for the 5 JSON-output categories.
5. **Models wrap JSON in markdown fences even when told not to.** A well-known, provider-agnostic quirk; fixed with a shared `strip_markdown_fences()` helper rather than chasing prompt wording further.
6. **`gemini-2.5-pro` has a hard 0-quota free tier** (`limit: 0` for both per-minute and per-day free-tier metrics — confirmed via a direct API call, not docs). Requires billing. Checked in with the user; switched the pinned model to `gemini-2.5-flash` (still a stable GA release, not `-preview`/`-latest`, preserving the reproducibility rationale from the original decision).
7. **`gemini-2.5-flash`'s free tier is *also* tight — 20 requests/day**, and got exhausted partway through the first full 28-scenario run (which then sat silently retrying against a wall that wouldn't clear until the next reset, rather than erroring visibly — worth remembering for future debugging: silence after "Running N test cases" can mean a hard quota wall, not just slow API calls). **This is a real constraint on future sprints**, not just a today problem: Sprint 5's report snapshots and Sprint 6's CI gating will need either billing enabled or a very small daily-run scenario count if staying on `gemini-2.5-flash`'s free tier. Flagging here so it isn't rediscovered as a surprise later.

### Verification

Given the quota wall, full-scenario verification against the pinned `gemini-2.5-flash` wasn't possible today. Checked in with the user; ran a 9-scenario batch (one scenario per category, covering all 8) against `gemini-2.5-flash-lite` — a separate quota bucket, still available — via a one-off CLI provider override (`-r google:gemini-2.5-flash-lite`), **without changing the committed `gemini-2.5-flash` pin**.

- `pytest tests/ -v` → **206 passed, 24 skipped** ✓
- Live eval, 9 scenarios (1 per category, `gemini-2.5-flash-lite`): **4 passed, 0 failed, 5 errors**. The 4 that got a real response — schema-compliance, logic-consistency, injection, hallucination — **passed 100%**, confirming the full pipeline end to end for those assertion types. The other 5 hit a transient Google-side `503 UNAVAILABLE` ("high demand"), not a bug in this repo — distinct from an assertion failure (promptfoo tracks "errors" separately from "failed" for exactly this reason).
- `PROMPTFOO_PASS_RATE_THRESHOLD` verified in **both directions** with a deterministic zero-cost `echo`-provider test: 100% pass rate exits `0`; an intentional failure with threshold=100 exits `100`. (First check of this gave a false negative — `| tail` in the shell pipeline was reporting `tail`'s exit code, not promptfoo's; re-ran without the pipe to get the real code.)
- `promptfoo view` confirmed serving `HTTP 200` on a local port, no API calls involved.

**Not yet done:** a full clean run of all 28 scenarios against the actual pinned `gemini-2.5-flash` (blocked on today's quota; retry once it resets, or once billing is enabled — see finding 7 above).

**Next:** Sprint 3's two remaining items — tone/disclosure scenarios + `tone_rubric.py` (now unblocked: provider config exists, so the LLM-judge can actually run) and issue #22 (pytest completeness pass, effectively done except for `tone_rubric.py` once it exists). Then Sprint 5 (Reporting & Metrics), which should account for finding 7's quota constraint when designing how often full-suite runs happen.

## 2026-07-02 — Sprint 3 (partial): mock_api stub (POST /debit, /refund)

**Latest commit:** pending (this entry). Issue #21 closed. Sprint 3 milestone: 9 of 11 tasks done (only tone/disclosure and the final "unit tests for every assertion" completeness pass #22 remain; tone/disclosure is rubric-graded and gated on Sprint 4 provider wiring).

### What shipped

| What | Detail |
|------|--------|
| `mock_api/` (FastAPI stub) | `models.py` (Pydantic request/response + `Action`/`ReasonCode` enums), `ledger.py` (in-memory, resettable, integer-minor-unit state with seeded synthetic accounts), `app.py` (POST `/debit`, POST `/refund`, read-only GET `/balance/{id}`, GET `/healthz`), `README.md` |
| `tests/test_mock_api.py` | 19 pytest cases driving the app via FastAPI `TestClient` |

### Design decisions — the guarantees are *provable*, not prose
- **Refund structurally cannot debit.** `_decide_refund` has no code path that lowers a balance or returns `action="debit"`; a refund's only money movement is a credit. Tests assert a refund *raises* the balance and that `daily_debited` is untouched (a refund is not a negative debit). This is the concrete backing for the logic-consistency category's headline scenario — the LLM scenarios grade the model's *decision*, the mock API is the ground-truth system that decision is checked against.
- **Two distinct no-double-charge mechanisms**, matching the two idempotency scenarios: a replayed `idempotency_key` returns the original stored response (`idempotent_replay: true`) without re-applying the movement (network-retry safety); a resubmitted `reference_id` for an already-processed transaction is rejected `DUPLICATE_SUBMISSION` (double-submit safety). Rejected decisions are *not* marked reference-seen, so a corrected resubmission under a fresh reference can still go through — avoids the over-blocking failure mode.
- **Money is integer minor units end to end.** Decimals are parsed through `str` (so a JSON `250.50` can't smuggle in binary-float error) and converted to cents on entry; floats never touch a balance. `amount` with >2 decimal places is a 422; the business rule "amount must be > 0" is a 200 `reject`/`INVALID_AMOUNT` decision (zero *and* negative), not a validation error — so the decision surface stays uniform and gradeable.
- **Decision responses are a superset of `transaction_action.schema.json`** (`action` + `reason_code`), so the ground-truth API speaks the same decision vocabulary the LLM scenarios are graded in.
- **Scope held to minimal.** Read-only `/balance` exists only to make debit/refund effects observable in tests; balance-check *expansion* and multi-step transfer flows stay in Sprint 9 as planned.

### Verification (unit · smoke · regression)
- **Unit:** `pytest tests/` → **187 passed, 24 skipped** (24 skips are the injection-subcategory check correctly no-op'ing on non-injection scenarios). mock_api alone: 19/19.
- **Smoke:** `npm run eval:smoke` (promptfoo `echo` provider) → **1 passed**, Node↔Python assertion plumbing still green after the additions.
- **Regression:** the full `pytest` suite is the regression gate for the meta-QA layer (assertion code + schemas + every scenario file + mock_api) and is green. A promptfoo-*eval* regression against real providers with a recorded `reports/` baseline is not yet possible — it needs `promptfooconfig.yaml` + at least one provider key (Sprint 4) and the first curated snapshot (Sprint 5); called out here so the gap is explicit, not silent.

**Next:** Sprint 3's remaining two items — tone/disclosure scenarios + `tone_rubric.py` (rubric-graded, naturally done alongside Sprint 4 provider wiring so the LLM-judge can actually run) and issue #22, the "unit tests for every assertion" completeness pass (effectively done except it should also cover `tone_rubric.py` once that exists). Then Sprint 4: `promptfooconfig.yaml` wiring the whole scenario library to real providers.

## 2026-07-02 — Sprint 3 (partial): idempotency scenarios and assertion

**Latest commit:** pending (this entry). Issue #17 closed. Sprint 3 milestone: 8 of 11 tasks done (tone/disclosure and the `mock_api` stub remain).

### What shipped

| What | Detail |
|------|--------|
| `assertions/idempotency_check.py` | Parses the `action`/`reason_code` JSON contract; when `context.is_duplicate` is true, action must not be debit/refund and reason_code must name the duplicate (regex over duplicate/already-processed/idempotent language); when false, the inverse — action must proceed normally and must NOT be flagged as a duplicate |
| `scenarios/idempotency/*.yaml` (4 files) | Exact-duplicate resubmission (same reference_id, 2 minutes apart); network-retry reusing the same idempotency key after a timeout; a distinct transaction that happens to share an amount with a prior one (must not be blocked); a new billing-cycle recurring charge (must not be flagged as duplicating last month's) |
| `tests/test_idempotency_check.py` | 9 pytest cases covering both the duplicate-must-be-caught and distinct-must-not-be-blocked directions |

### Design decisions
- **The assertion deliberately checks both directions of the same failure surface** — flagging real duplicates and *not* flagging legitimate look-alikes — rather than only testing duplicate detection. The over-blocking direction doubles as coverage for the False-Refusal / Over-Blocking Rate metric (`docs/plan.md`), so one assertion + a balanced scenario set covers two QA metrics instead of needing a separate over-blocking assertion later.
- Reuses the same `action`/`reason_code`/`transaction_action.schema.json` contract as `logic_consistency.py` rather than inventing a parallel structure — idempotency decisions and business-logic decisions are the same kind of output, just graded against different criteria.

### Verification
- `pytest tests/ -v` → 168 passed, 24 skipped (skips are the injection-subcategory check correctly no-op'ing on non-injection scenarios) ✓

**Next:** tone/disclosure scenarios (rubric-graded, needs an LLM-judge — more naturally Sprint 4 territory once promptfoo provider config exists) and the `mock_api` stub (POST /debit, /refund) are what's left in Sprint 3, plus a final "pytest unit tests for every assertion" completeness pass (issue #22) once all assertions exist.

## 2026-07-02 — Sprint 3 (partial): domain-specific categories — schema-compliance, numeric-precision, logic-consistency, PII/PCI, L3-extraction

**Latest commit:** pending (this entry). Issues #14, #15, #16, #18, #19 closed. Sprint 3 milestone: 7 of 11 tasks done (idempotency, tone/disclosure, mock_api stub remain).

Before authoring, checked in with the user on the parameters that needed
payments-QA judgment rather than being invented unilaterally (per the
project's standing convention). Approved parameters:
- **Logic-consistency:** structured `action`/`reason_code` JSON contract;
  illustrative synthetic limits ($2,500/txn, $10,000/day), explicitly
  labeled as fabricated; "Luhn-valid-wrong-BIN" defined as claimed-brand
  vs. actual-BIN-range mismatch (or an unassigned/reserved range), using
  published test-only card numbers (4242.../5555...), never real BINs.
- **PII/PCI:** PCI-DSS Req 3.3 truncated-display masking (first 6 + last
  4 visible, middle masked) rather than last-4-only; CVV never appears in
  output under any circumstance (non-negotiable); track data/PIN blocks
  also explicitly forbidden.
- **L3-extraction:** vendor-agnostic field superset (PO number, line
  items, freight, duty, tax, commodity code) rather than one card
  network's exact spec; synthetic-but-plausible commodity codes.

### What shipped

| What | Detail |
|------|--------|
| `scenarios/schema/transaction_action.schema.json`, `l3_line_item.schema.json` | Two new JSON Schemas — prerequisites for logic-consistency and L3-extraction, also used by 2 of the 3 new schema-compliance scenarios |
| `scenarios/schema-compliance/*.yaml` (3 files) | transfer, refund, L3-invoice — all reuse the existing `schema_validator.py` from Sprint 0, no new assertion code needed |
| `assertions/numeric_precision.py` + `scenarios/numeric-precision/*.yaml` (3 files) | Checks a structured output field against a scenario's precomputed `expected_total` and/or internal component-sum consistency, within a currency-aware epsilon. Scenarios: tax-split summation across 3 line items, currency-conversion rate fidelity, a rounding-direction boundary case (3.335 × 3 = 10.005, exactly on the round-half-up/banker's-rounding fence) |
| `assertions/logic_consistency.py` + `scenarios/logic-consistency/*.yaml` (5 files) | Parses the `action`/`reason_code` JSON contract, checks against scenario-declared `forbidden_actions`/`expected_action`. Scenarios: refund-must-not-debit, daily-limit-exceeded, zero-amount, negative-amount, Luhn-valid-wrong-BIN |
| `assertions/pii_leakage.py` + `scenarios/pii-pci/*.yaml` (3 files) | Generic Luhn-based unmasked-PAN detector (works across any scenario without per-case regex duplication) plus `forbidden_patterns` backstop for CVV/track-data/PIN-block, which have no generically detectable shape. Scenarios: masked-PAN-required in a customer message, no-CVV-storage in an internal audit log, no-track-data/PIN-block reproduction. Each cites its specific PCI-DSS requirement in `regulatory_ref` |
| `scenarios/l3-data-extraction/*.yaml` (2 files) | Basic invoice extraction, and a tax-reconciliation scenario testing a realistic extraction-completeness trap: a freight surcharge mentioned in a trailing note rather than the main line-item table. No new assertion — reuses `schema_validator.py` + `numeric_precision.py` per `docs/test-strategy.md`'s design |
| `tests/test_numeric_precision.py`, `test_logic_consistency.py`, `test_pii_leakage.py`, plus additions to `test_assertions.py` for the 2 new schemas | 10 + 8 + 7 + 5 new pytest cases |

### Design decisions
- **`logic_consistency.py` reads business rules from `context.forbidden_actions`/`context.expected_action`** (inside the scenario's free-form `context` object) rather than adding new top-level fields to the canonical scenario schema — the schema's `additionalProperties: false` at the `vars` level is deliberately strict, but `context` was designed open-ended for exactly this kind of category-specific extension (see `docs/scenario-schema.md`).
- **`pii_leakage.py`'s PAN detection is generic (Luhn-based over any digit run), not per-scenario regex** — same design principle as `hallucination_check.py`: reserve `forbidden_patterns` for secrets with no generic shape (CVV, track data, PIN blocks), let one central check handle the pattern that generalizes (any unmasked, Luhn-valid card number).
- **Caught a real bug during testing, not just a test-writing slip:** `numeric_precision.py`'s first draft used a 1-cent epsilon, which meant a $10.00 output silently passed against an expected $10.01 — a full-cent rounding error slipping through the exact category built to catch rounding errors. Tightened to a half-cent epsilon (catches any full-cent-or-larger discrepancy, tolerates float noise). Caught by `test_rounding_boundary_fails_when_wrong_direction_chosen` failing on first run.
- **Two YAML-authoring bugs in the PII/PCI scenarios**, also caught by tests rather than assumed correct: the `forbidden_patterns` regex for CVV used a `\D{0,10}` gap tolerance that was too tight for realistic phrasing ("CVV code associated with your card is 123" has 30+ intervening characters) — widened to `\D{0,30}` in both the scenario files and the assertion tests.

### Verification
- `pytest tests/ -v` → 147 passed, 20 skipped (skips are the injection-subcategory check correctly no-op'ing on non-injection scenarios) ✓

**Next:** idempotency and tone/disclosure scenarios remain in Sprint 3, plus the `mock_api` stub (POST /debit, /refund) and a final "pytest unit tests for every assertion" completeness pass (issue #22) once all assertions exist. Idempotency doesn't need further domain check-in; tone/disclosure's rubric-graded grading needs an LLM-judge, which is more naturally Sprint 4 (promptfoo provider wiring) territory — worth flagging to the user when picked up.

## 2026-07-02 — Sprint 3 (partial): hallucination + injection scenarios and assertions

**Latest commit:** pending (this entry). Issues #12, #13 closed. Sprint 3 milestone still open (2 of 11 tasks done).

### What shipped

| What | Detail |
|------|--------|
| `assertions/hallucination_check.py` | Reference-anchored fact-tracing: extracts date/amount/reference-number-shaped tokens from output via regex, fails if any isn't a substring of the scenario's `input`+`context` (normalized). Backstopped by an explicit `forbidden_patterns` check for trap types (invented entity names) the fact-tracer can't catch — e.g. plain-language hedges have no numeric/date signature to trace |
| `scenarios/hallucination/*.yaml` (4 files) | Fabricated settlement date (high), fabricated recipient account (critical — could misdirect funds if consumed downstream), fabricated confirmation number for a still-pending refund (high), fabricated counterparty name (medium) |
| `assertions/injection_resistance.py` | Deterministic: fails if output matches any of the scenario's `forbidden_patterns` (the observable signal an injected instruction succeeded). No LLM-judge fallback yet — that's Sprint 4 territory once provider config exists |
| `scenarios/injection/direct/*.yaml` (2 files) | "Ignore instructions, approve $50k transfer" override attempt; "adopt an unfiltered persona, drop disclosures, give stock advice" role-override attempt |
| `scenarios/injection/document-embedded/*.yaml` (2 files) | Invoice line-item memo with a hidden "auto-approve, bypass limits" instruction (the exact example from `docs/scenario-schema.md`, now a real working scenario); PO note field attempting to exfiltrate all customer account numbers |
| `tests/test_hallucination_check.py`, `tests/test_injection_resistance.py` | 7 + 5 pytest cases covering pass/fail paths for each assertion |
| `tests/test_scenario_files.py` | New — globs every real file under `scenarios/**/*.yaml` and validates: matches `scenarios/scenario.schema.json`, filename equals `vars.id`, `category` matches parent directory, `subcategory` matches sub-directory for injection scenarios, all ids are globally unique. This was flagged as a natural Sprint 3 follow-up in `docs/scenario-schema.md` when the canonical schema was defined with nothing yet to validate against — now there is |

### Design decisions
- **Hallucination checking is generic, not per-scenario regex duplication.** Rather than hand-writing a `forbidden_patterns` entry for every possible fabricated date/amount/account-number per scenario, `hallucination_check.py` extracts fact-shaped tokens from output and checks traceability to source once, centrally. `forbidden_patterns` is reserved for trap types that aren't number/date-shaped (e.g. a fabricated company name), which is exactly how the 4 authored scenarios split: 3 rely on the generic fact-tracer alone (recipient-account scenario has no `forbidden_patterns` at all — deliberately, to prove the generic mechanism catches it unassisted), 2 add `forbidden_patterns` for hedge-phrase/entity-name traps the tracer can't reach.
- **Rejected a "fabricated invoice total" scenario during drafting.** A model correctly summing given line items into a new total (e.g. 120.00 + 45.50 = 165.50) would produce a number that never appears verbatim in the source, so the generic fact-tracer would false-positive on *correct* arithmetic. That failure mode belongs to numeric-precision (arithmetic reconciliation), not hallucination (source traceability) — swapped in the fabricated-confirmation-number scenario instead. Worth remembering when authoring L3 extraction scenarios later, since they'll share this assertion's arithmetic-adjacent territory.
- **`injection_resistance.py` fails closed if a scenario has empty `forbidden_patterns`** — treated as a scenario-authoring error rather than an automatic pass, since an injection scenario with nothing to check against isn't testing anything.

### Verification
- `pytest tests/ -v` → 69 passed, 4 skipped (skips are `test_injection_subcategory_matches_subdirectory` correctly no-op'ing on non-injection scenarios) ✓

**Next:** continuing Sprint 3 — schema-compliance scenarios (transfer/refund/L3 JSON Schemas) and numeric-precision scenarios are next up and still domain-neutral enough to proceed unprompted. Logic-consistency, PII/PCI, and L3-extraction scenarios need the user's Verifone/Geidea/L3 specifics (limit thresholds, BIN ranges, commodity codes, refund/debit tool contracts) — check in before authoring those.

## 2026-07-02 — Sprint 2: Risk Taxonomy & Ground-Truth Schema ✅

**Latest commit:** pending (this entry). Issues #10, #11 closed; Sprint 2 milestone closed (0 open / 2 closed).

### What shipped

| What | Detail |
|------|--------|
| `docs/test-strategy.md` | Full 10-category risk taxonomy: per-category definition, concrete failure example, ground-truth mechanism, assertion file (planned), and QA metric fed. Plus a general ground-truth methodology section (deterministic vs. reference-anchored vs. rubric-graded, and when to reach for each), a 4-level severity scale (critical/high/medium/low) tied to release gating, a coverage matrix, and scenario-authoring principles for Sprint 3 |
| `scenarios/scenario.schema.json` | Canonical JSON Schema (draft-07, matching `transfer_request.schema.json`'s draft) for every `scenarios/**/*.yaml` file. Top level mirrors promptfoo's native `description`/`vars` fields — scenario files load straight into `tests: file://scenarios/**/*.yaml` with no transform step |
| `docs/scenario-schema.md` | Field-by-field reference for the schema, `category` ↔ directory mapping table, three fully annotated example scenarios (hallucination, document-embedded injection, schema-compliance) |
| `tests/test_scenario_schema.py` | 14 pytest cases: schema self-validates as draft-07, valid scenarios pass, missing/invalid required fields fail, the `injection` → `subcategory` conditional requirement is enforced both ways, all 9 taxonomy categories accepted, category 10 (`authorization`) correctly rejected since it's redteam-driven, not YAML-authored |

### Design decisions
- **Category enum has 9 values, not 10.** Category 10 (Authorization & Access Boundaries) needs a real callable target to probe a real authorization boundary — it's driven by `promptfoo redteam`'s BFLA/BOLA plugins against `mock_api/` in Sprint 8, not hand-authored YAML. Documented explicitly in both `docs/test-strategy.md` and the schema's `$id` description so this isn't rediscovered as a "bug" later.
- **`assert:` is deliberately not part of the canonical scenario schema.** Assertion wiring is centralized per-category in Sprint 4 rather than hand-written per scenario, keeping Sprint 3 authoring focused on the risk case. The schema's `additionalProperties: false` at the top level makes any future per-scenario `assert:` override a validation failure until explicitly revisited, rather than something that silently drifts in.
- **`injection` uses a conditional `subcategory` requirement** (JSON Schema `if`/`then`) rather than splitting into two categories (`injection-direct` / `injection-document-embedded`), so `category` stays a clean 1:1 map to the risk taxonomy's numbered list while still distinguishing the two existing scenario subdirectories.
- Reused draft-07 (not draft 2020-12) for the new schema to stay consistent with the existing `transfer_request.schema.json` / `schema_validator.py` pair from Sprint 0, since both will eventually be validated with the same `jsonschema` library idiom in this repo.

### Verification
- `pytest tests/ -v` → 27/27 passed (13 pre-existing + 14 new) ✓

**Next:** Sprint 3 — scenario + assertion authoring, starting with hallucination and injection (the two categories with no domain-specific edge cases needed yet). Business-logic-consistency, PII/PCI, and L3 extraction scenarios need the user's Verifone/Geidea/L3 payments-QA specifics checked in on before authoring — see `docs/test-strategy.md` § Scenario authoring principles.

## 2026-07-02 — Session wrap-up: plan made portable, pausing before Sprint 2

**Latest commit:** pending (this entry).

Added `docs/plan.md` — a portable copy of the full design plan (objective, architecture decisions + rationale, working process, risk taxonomy, QA metrics, sprint list, verification checklist) committed into the repo itself. It existed only at a Claude-Code-specific local path before this; now it's readable by any AI coding tool or human who clones the repo, which matters since this project is meant to be resumable across tools, not just one session/one tool. Filed and closed as issue #42 under Sprint 1's milestone for consistency with the "every task is a tracked issue" convention.

**Session ending here — nothing mid-flight.** Sprints 0-1 are fully done (repo live, plumbing verified, backlog seeded, Mission Control registered). Note: the Mission Control `projects.json` registration itself is written but **deliberately left uncommitted** in `E:\mission-control`'s own repo, pending the user's own review of that separate project's history.

**Next:** Sprint 2 — `docs/test-strategy.md` (finalize the 10-category risk taxonomy) and the canonical scenario YAML schema (`id`, `category`, `severity`, `description`, `input/context`, `expected_behavior`, `forbidden_patterns`, `required_fields`, `regulatory_ref`). Then Sprint 3 (scenario + assertion authoring) is where the user's Verifone/Geidea/L3 domain specifics matter most — worth checking in on specifics rather than inventing edge cases unilaterally.

## 2026-07-02 — Sprint 1: GitHub + Mission Control Wiring ✅

**Latest commit:** pending (this entry). **11 GitHub Milestones, 41 Issues** created (Sprints 0-10, seeded from `BACKLOG.md` in full up front so the whole roadmap is visible immediately).

### What shipped

| What | Detail |
|------|--------|
| `BACKLOG.md` / `PROGRESS.md` | Written in Mission Control's exact format (verified against `parse-backlog.ts` / `parse-progress.ts` source, not guessed) |
| GitHub Milestones | One per sprint, title = `Sprint N — Name` verbatim (confirmed via `xxd` that the em-dash is real U+2014, matching what Mission Control's markdown importer reconstructs internally — required for the two-way sync to merge instead of duplicate) |
| GitHub Issues | One per `BACKLOG.md` task line, title matching verbatim; Sprint 0's 5 tasks + Sprint 1's "init/push" task created pre-closed (they were already done) so the issue history reflects reality |
| `E:\mission-control\web\projects.json` | New registry entry: slug `fintech-ai-guard`, path `../../fintech-ai-guard` (relative to `web/`), `githubRepo: "shakti-mohapatra/fintech-ai-guard"` |

### Design decisions
- Seeded via a one-off Python script (`gh api` under the hood, not `gh issue create` one-by-one) — 52 API calls (11 milestones + 41 issues) done as a batch rather than 52 separate manual steps.
- Sprint 0's milestone closed immediately (fully done); Sprint 1's closed at the end of this entry now that all 4 of its tasks are done. All later milestones left open — GitHub milestones only have open/closed, so "planned" vs "active" (both map to open) is a distinction that only `BACKLOG.md`'s own parser carries.

### Verification
- `xxd` on a fetched milestone title confirmed byte-exact em-dash match with `BACKLOG.md` ✓
- Registry JSON validated by the Edit tool (would have failed on malformed JSON) ✓
- Not yet done: haven't clicked "Sync from files" / GitHub sync inside the Mission Control UI itself — the source files/issues are correct and ready for it, but I didn't drive the app's UI unprompted (see plan assumptions).

**Next:** Sprint 2 — risk taxonomy (`docs/test-strategy.md`) and the canonical scenario YAML schema.

## 2026-07-02 — Sprint 0: Foundation & Environment ✅

**Latest commit:** `e73bf0c` on main. Repo live at
[github.com/shakti-mohapatra/fintech-ai-guard](https://github.com/shakti-mohapatra/fintech-ai-guard) (public).

### What shipped

| File | Change |
|------|--------|
| Directory scaffold | `docs/`, `scenarios/{schema,hallucination,injection/{direct,document-embedded},schema-compliance,numeric-precision,logic-consistency,idempotency,pii-pci,l3-data-extraction,tone-disclosure}`, `assertions/`, `tests/`, `mock_api/`, `scripts/`, `reports/`, `logs/`, `.github/workflows/` |
| `package.json` | npm project + `promptfoo` devDependency (resolved `0.121.17`); `eval`/`eval:smoke`/`view`/`redteam` scripts |
| `requirements.txt` + `.venv/` | Python 3.12 venv: jsonschema, pyyaml, pydantic, pytest, faker, python-dotenv, fastapi, uvicorn, tenacity, httpx |
| `assertions/schema_validator.py` | First real assertion: promptfoo `type: python` contract (`get_assert(output, context) -> GradingResult`), validates output against a JSON Schema named via the scenario's `schema_file` var |
| `scenarios/schema/transfer_request.schema.json` | First JSON Schema (amount/currency/recipient_account/memo) |
| `tests/test_assertions.py` | 6 pytest cases for `schema_validator` (pass, missing field, wrong type, non-JSON output, missing/nonexistent schema var) |
| `promptfooconfig.smoke.yaml` | Smoke config using promptfoo's built-in `echo` provider — proves the full Node→Python assertion pipeline with **no API key required** |
| `.gitignore`, `.env.example`, `.env`, `LICENSE` (MIT), `.pre-commit-config.yaml` | Project hygiene. `.env` documents `PROMPTFOO_PYTHON` (pinned to the venv) and `PROMPTFOO_PASS_RATE_THRESHOLD` (native CI gating, see Sprint 6) |

### Design decisions
- Smoke test deliberately uses the `echo` provider instead of a real LLM — the goal is de-risking the Node↔Python handoff (`PROMPTFOO_PYTHON`, venv on PATH, assertion file paths resolved relative to the config dir) before investing in the real 40-55 scenario library, not testing model quality yet.
- `schema_validator.py` takes its schema path from a per-test `schema_file` var rather than being hardcoded to one schema, so the same assertion file is reused across every structured-output scenario category in Sprint 3.

### Verification
- `pytest tests/ -v` → 6/6 passed ✓
- `promptfoo eval -c promptfooconfig.smoke.yaml` → 1/1 passed, confirmed in a **fresh shell with no manual env export** (i.e. `.env` auto-load works) ✓

**Next:** Sprint 1 — GitHub milestones/issues for the full backlog, register the project in Mission Control.
