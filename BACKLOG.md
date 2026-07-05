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

## Sprint 8 — Red-Teaming
- [ ] Wire promptfoo redteam for injection, jailbreak, PII, and excessive-agency plugins
- [ ] Wire BFLA/BOLA redteam plugins against the mock API
- [ ] Document red-team findings in a dedicated report section

## Sprint 9 — Full Agentic Mock-API Buildout
- [ ] Expand mock_api with balance checks and multi-step transfer flows
- [ ] Author richer function-calling scenarios against the expanded mock API

## Sprint 10 — Trend Dashboard
- [ ] Build a static dashboard (GitHub Pages or Streamlit) plotting metric trends across reports/ history
