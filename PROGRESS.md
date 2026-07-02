# Progress Log — Fintech-AI-Guard

A running log so multi-day work is easy to pick back up. Newest entry on top.

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
