# Backlog — Fintech-AI-Guard

**Agile & living.** Re-order, add, drop, or rewrite tasks freely as requirements
change. Each task mirrors a **GitHub Issue**; each sprint mirrors a **GitHub
Milestone** — see [github.com/shakti-mohapatra/fintech-ai-guard](https://github.com/shakti-mohapatra/fintech-ai-guard).

> Convention: `[ ]` = to do, `[~]` = partially done, `[x]` = done. When you
> finish a task, tick it here, close the GitHub Issue, and note it in
> `PROGRESS.md`.

## Sprint 0 — Foundation & Environment ✅
- [x] Scaffold repo directory structure (docs/, scenarios/, assertions/, tests/, mock_api/, scripts/, reports/, logs/, .github/workflows/)
- [x] Initialize npm and install promptfoo as a devDependency
- [x] Set up Python venv and requirements.txt (jsonschema, pydantic, pytest, faker, fastapi, tenacity, etc.)
- [x] Add .gitignore, .env.example, MIT LICENSE, pre-commit config
- [x] Build schema_validator.py assertion and prove the Node/Python eval pipeline end-to-end with the echo provider (no API key required)

## Sprint 1 — GitHub + Mission Control Wiring ✅
- [x] Initialize git, create the public GitHub repo, and push
- [x] Write BACKLOG.md and PROGRESS.md in Mission Control's format
- [x] Create GitHub milestones for every sprint and issues for every task
- [x] Register fintech-ai-guard in Mission Control's projects.json
- [x] Copy the full design plan into docs/plan.md so any AI tool can resume the project, not just the one that started it

## Sprint 2 — Risk Taxonomy & Ground-Truth Schema ✅
- [x] Write docs/test-strategy.md defining the 10-category risk taxonomy
- [x] Define the canonical scenario YAML schema (id, category, severity, description, input/context, expected_behavior, forbidden_patterns, required_fields, regulatory_ref)

## Sprint 3 — Scenario + Assertion Authoring ✅
- [x] Author hallucination scenarios and their assertion
- [x] Author direct and document-embedded injection scenarios and their assertion
- [x] Author schema-compliance scenarios (transfer, refund, L3 line-item JSON Schemas)
- [x] Author numeric-precision scenarios and numeric_precision.py assertion
- [x] Author logic-consistency scenarios (refund-vs-debit, limits, boundary/zero/negative amounts, Luhn-valid-wrong-BIN) and logic_consistency.py assertion
- [x] Author idempotency scenarios and idempotency_check.py assertion
- [x] Author PII/PCI scenarios and pii_leakage.py assertion
- [x] Author L3 data-extraction scenarios
- [x] Author tone/disclosure scenarios and tone_rubric.py assertion
- [x] Build the minimal mock_api stub (POST /debit, POST /refund) for provable business-logic testing
- [x] Write pytest unit tests for every assertion

## Sprint 4 — promptfoo Wiring ✅
- [x] Write promptfooconfig.js (not .yaml — see PROGRESS.md) with multi-provider support (Claude Sonnet 5, GPT-5.5 [unverified], Gemini 2.5 Flash)
- [x] Wire PROMPTFOO_PASS_RATE_THRESHOLD for native CI gating
- [x] Verify promptfoo eval and promptfoo view run cleanly across the scenario set

## Sprint 5 — Reporting & Metrics
- [x] Write scripts/generate_report.py to compute the QA metrics table
- [x] Write scripts/run_eval.py as a local convenience wrapper
- [x] Snapshot the first curated run into reports/ and regenerate evaluation_report.md — blocked on free-tier quota (32 scenarios > 20 req/day on gemini-2.5-flash); see issue #28

## Sprint 6 — CI/CD ✅ (reworked 2026-07-05 — see docs/antigravity-review-2026-07-05.md)
- [x] Add .github/workflows/eval.yml using promptfoo/promptfoo-action — rewritten: added required `config: promptfooconfig.js` input, gate via `fail-on-threshold: 95` action input, eval job restricted to `workflow_dispatch` + nightly `schedule` (push/PR only run the free pytest job — no accidental paid runs), added separate pytest job.
- [x] promptfooconfig.js — reverted antigravity's model downgrade back to `anthropic:messages:claude-sonnet-5`.
- [ ] Configure GitHub Actions repo secrets for provider API keys — MANUAL / USER-ONLY (repo Settings → Secrets and variables → Actions: `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`). Nothing else in Sprint 6 depends on this being done immediately — the eval job won't fire until you manually dispatch it or the nightly cron hits.

## Known Issues
- [x] Fixed 2026-07-05: 3 pytest failures in tests/scripts/test_run_eval.py were Windows-local (run_eval.py uses `npx.cmd` on win32, tests hardcoded `"npx"`). Tests now derive the expected binary from `sys.platform`. Full suite: 248 passed, 28 skipped, 0 failed.

## Sprint 7 — Documentation Polish
- [x] Write the README as a technical spec with real metrics and an architecture diagram
- [x] Write docs/architecture.md
- [x] Write docs/compliance-mapping.md (assertion -> PCI-DSS clause mapping)
- [x] Write docs/metrics.md including the cross-run consistency methodology
- [x] Add the synthetic-data-only disclaimer to README and docs

## Sprint 8 — Red-Teaming ✅
- [x] Wire promptfoo redteam for injection, jailbreak, PII, and excessive-agency plugins — PII (4 subcategories), excessive-agency, and `indirect-prompt-injection` (fixed Sprint 14) all ran live and passed. `jailbreak` is a promptfoo *strategy*, not a plugin (Sprint 14 finding) — correctly wired under `strategies:` in `promptfooconfig.redteam.yaml`, deliberately excluded from the smoke tier to protect quota.
- [x] Wire BFLA/BOLA redteam plugins against the mock API — both ran live 2026-07-09, 1/1 passed each both runs. `redteam.authz` can now optionally log to a file (Sprint 14, `REDTEAM_AUTHZ_LOG_PATH`) for independent structural-block confirmation alongside the LLM-judge verdict.
- [x] Document red-team findings in a dedicated report section — `evaluation_report.md` § Red-Team Findings, from `eval-Ob2-2026-07-09T08:20:44`

## Sprint 9 — Full Agentic Mock-API Buildout ✅
- [x] Expand mock_api with balance checks and multi-step transfer flows
- [x] Author richer function-calling scenarios against the expanded mock API — reverted 2026-07-06 (`docs/antigravity-review-2026-07-06.md`); design `docs/sprint9-function-calling-design.md`, implemented 2026-07-09, Groq target added + live-verified 2026-07-10 (fc:smoke 8/8 + main eval 60/60, 0 error rows on Groq; Gemini flash-lite quota-exhaustion confirmed as the known/expected blocker)
  - [x] 9.1 Add `transfer_tool` to `scripts/agent_target.py`'s tool list (mock_api `/transfer` existed but was never wired to the tool-calling target)
  - [x] 9.2 Extend `agent_target.py.call_api`'s return with a `metadata.tool_calls` trace
  - [x] 9.3 New parallel pipeline: `promptfooconfig.functioncalling.yaml` + `scripts/agent_target_fc.py` (ledger-reset wrapper, `maxConcurrency: 1`) + `scenarios-function-calling/*.yaml` + `assertions/function_calling.py` — deliberately not wedged into `scenarios/**/*.yaml`'s closed schema, same precedent as Category 10/redteam
  - [x] 9.4 Author 8 v1 scenarios per the design doc's table (tool-selection, sequencing, rejection-honesty, idempotency, numeric-fidelity — not re-testing authz, that's redteam's job); scenarios written, pytest 411/50/0 green. Live-verified 2026-07-10 via Groq target (`fintech-agent-fc-groq`, llama-3.3-70b-versatile) after Gemini's flash-lite quota stayed exhausted: 8/8 scenarios returned real output (2 pass, 5 assertion-fail, 1 hit max-tool-turns safeguard), zero error-placeholder rows
  - [x] 9.5 `docs/test-strategy.md`: add Category 11 (Agentic Tool-Use / Function-Calling Correctness) + coverage-matrix row

## Sprint 10 — Trend Dashboard
- [x] Build a static dashboard (GitHub Pages or Streamlit) plotting metric trends across reports/ history

## Sprint 11 — Negative & Boundary Scenario Hardening
Full gap analysis and approved targets: `docs/sprint11-test-hardening-plan.md`.
- [x] 11.1 Author +28 negative/boundary scenarios across categories 1-9 (chunked per category, not one commit)
  - [x] Hallucination: +2 (invented total/subtotal, invented fee/rate) — `hallucination-fabricated-invoice-total-005`, `hallucination-fabricated-fee-rate-006`
  - [x] Injection (direct): +3 (base64-obfuscated, multi-turn planted instruction, trusted-field spoof) — `injection-direct-base64-obfuscated-003`, `injection-direct-multiturn-planted-instruction-004`, `injection-direct-trusted-field-spoof-005`
  - [x] Injection (document-embedded): +3 (table-cell instruction, cross-document split, fake compliance directive) — `injection-document-embedded-table-cell-instruction-003`, `injection-document-embedded-cross-document-split-004`, `injection-document-embedded-fake-compliance-directive-005`
  - [x] Schema Compliance: +3 (recipient boundary length, numeric type fidelity, no additional fields) — `schema-compliance-transfer-recipient-boundary-length-004`, `schema-compliance-numeric-type-fidelity-005`, `schema-compliance-no-additional-fields-006`
  - [x] Numeric Precision: +4 (zero-decimal currency, negative discount, multi-step conversion, percentage-tax rounding) — `numeric-precision-zero-decimal-currency-004`, `numeric-precision-negative-discount-application-005`, `numeric-precision-multi-step-conversion-006`, `numeric-precision-percentage-tax-rounding-007`
  - [x] Logic Consistency: +4 (exactly-at-limit, exactly-drains-balance, refund-exact-remaining, closed-account) — `logic-consistency-amount-exactly-at-daily-limit-006`, `logic-consistency-amount-exactly-drains-balance-007`, `logic-consistency-refund-exact-remaining-balance-008`, `logic-consistency-closed-account-debit-attempt-009`
  - [x] Idempotency: +3 (same-key-different-payload, key-reused-across-endpoints, reference-id-reused-different-amount) — `idempotency-same-key-different-payload-005`, `idempotency-key-reused-across-endpoints-006`, `idempotency-reference-id-reused-different-amount-007`
  - [x] PII/PCI: +3 (IBAN/SWIFT masking, leakage-in-error-message, leakage-in-dispute-narrative) — `pii-pci-iban-swift-masking-004`, `pii-pci-leakage-in-error-message-005`, `pii-pci-no-pan-in-dispute-narrative-006`
  - [x] L3 Data Extraction: +3 (total-reconciliation-mismatch, fractional-quantity-precision, no-fabricated-surcharge) — `l3-data-extraction-total-reconciliation-mismatch-003`, `l3-data-extraction-fractional-quantity-precision-004`, `l3-data-extraction-no-fabricated-surcharge-005`
- [x] 11.2 Sanity-tier pytest after each category, full regression at sprint close — final regression: **353 passed, 50 skipped, 0 failed** (verified from a clean `pip install`, see PROGRESS.md)
- [x] 11.3 Update docs/test-strategy.md / docs/compliance-mapping.md if any new scenario adds a regulatory_ref — none of the new scenarios cite a PCI-DSS clause not already present in `docs/compliance-mapping.md`, so no doc changes were needed
- [x] 11.4 Confirm new scenarios load into promptfoo cleanly, no live paid-API run — `npx promptfoo validate -c promptfooconfig.js` -> "Configuration is valid." (static config/schema check, makes no provider calls)

## Sprint 12 — Meta-QA Hardening & API Request-Validation/Error-Handling
Full matrix: `docs/sprint11-test-hardening-plan.md` section 2A.
- [x] Add pytest-cov, publish coverage % in docs/metrics.md — pinned `pytest-cov==7.1.0` (verified-working, not the plan's placeholder 6.0.0); **89% overall** across assertions/mock_api/scripts
- [x] Add prompts/build_prompt.js unit tests — 6 new tests via a Node subprocess bridge (`tests/prompts/_run_build_prompt.js`), zero API cost
- [x] Add ~24 mock_api request-validation/boundary/error-handling/concurrency tests (section 2A) — 32 new test items added (28 unique + 4 parametrized), `mock_api/app.py` now at 100% coverage
- [x] Add audit-log leakage test tied to new PII/PCI scenario — added; **found a real gap** (see PROGRESS.md), tracked as a documented `xfail`, not silently patched

## Sprint 13 — Red-Team Go-Live (Sprint 8 close-out)
Code complete since Sprint 8 (`docs/sprint8-implementation-plan.md`); blocked purely on a live-API go-ahead.
- [x] 13.1 Confirm current Gemini free-tier quota (direct curl check) — 2026-07-09, live curl to `gemini-2.5-flash:generateContent` returned 200 (first attempt hit a transient 503, retried)
- [x] 13.2 Explicit go-ahead ask before running the redteam scan — user approved 2026-07-09; ran via `promptfoo redteam run` (not `npm run redteam:smoke`/`redteam eval`, which don't generate adversarial test cases — see Sprint 14)
- [x] 13.3 Run generate_redteam_report.py, append findings to evaluation_report.md — fixed a real bug in the script first (it read `vars.pluginId`, but promptfoo's export puts it at `result.metadata.pluginId` — every row was rendering as `(unknown plugin)`); regression-tested (`tests/scripts/test_generate_redteam_report.py`, 3/3 pass) before trusting the output
- [x] 13.4 Tick Sprint 8's boxes — done above; `indirect-prompt-injection` and `jailbreak` gaps intentionally left open rather than papered over, tracked as Sprint 14

## Sprint 14 — Red-Team Coverage Gaps (found during Sprint 13's live run) ✅
- [x] Fix `indirect-prompt-injection` plugin: set `config.indirectInjectionVar: 'prompt'` in `promptfooconfig.redteam.smoke.yaml` and `promptfooconfig.redteam.yaml` (confirmed default var name against a real generated `redteam.yaml` — no `prompts:` block in either config, so promptfoo falls back to `prompt`, matching `agent_target.py`'s `call_api(prompt, ...)`). Verified live 2026-07-09: plugin generated and ran (previously silently skipped).
- [x] `jailbreak` — **not a plugin**, corrected instead of added: verified against the installed `promptfoo` package's own strategy registry (`node_modules/promptfoo/dist/src/strategies-CSRF0f2a.cjs`) that `jailbreak` is a **strategy** id, not a plugin id, and doesn't take `numTests` (strategies multiply existing plugin test cases instead). Sprint 8's original wording was loose. `promptfooconfig.redteam.yaml` already has it correctly under `strategies:`; left out of the smoke tier on purpose, per the smoke config's own quota-protection rationale (a strategy would multiply, not add 1, test case).
- [x] Piped `redteam.authz`'s logger to a file via opt-in `REDTEAM_AUTHZ_LOG_PATH` env var (`scripts/redteam_authz.py`) — off by default so pytest runs don't pollute a "real run" log with test events. Verified live 2026-07-09: file created, valid (empty) jsonl — this run's bola/bfla cases had the model refuse verbally before ever calling a tool, so the structural guard genuinely wasn't exercised (honest 0, not a broken mechanism — see PROGRESS.md).
- [x] (found while regenerating the report) `scripts/generate_redteam_report.py` appended a second `## Red-Team Findings` section instead of replacing the first on a re-run — fixed to replace in place; regression test added.
