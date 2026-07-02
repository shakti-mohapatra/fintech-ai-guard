# Progress Log — Fintech-AI-Guard

A running log so multi-day work is easy to pick back up. Newest entry on top.

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
