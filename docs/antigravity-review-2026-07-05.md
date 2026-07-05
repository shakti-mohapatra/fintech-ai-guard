# Antigravity Sprint 6 Review — 2026-07-05

Independent verification of the work done by the Antigravity agent
(git author `Caveman Ultra <caveman@antigravity.ai>`) on Fintech-AI-Guard,
before any paid-API eval was run. Reviewer: Claude Code (Opus 4.8).

## Verdict: 🔴 NOT GREEN at review time → 🟢 FIXED 2026-07-05

The eval was correctly halted before spending API money — the change
Antigravity staged would have run against the wrong model, and the workflow
it wrote would not have gated correctly. All findings below were fixed in
the same session (see PROGRESS.md's "Sprint 6 (reworked after review)"
entry): `eval.yml` rewritten with the required `config:` input, real
`fail-on-threshold` gate, eval restricted to `workflow_dispatch`/nightly
only, a separate free pytest job added, the model downgrade reverted, and
the Windows-only pytest failures fixed. Full suite is green: 248 passed, 28
skipped, 0 failed. Antigravity is clear to resume smaller/well-scoped tasks
from BACKLOG.md going forward — this doc stays as the record of what its
first Sprint 6 pass got wrong.

## What Antigravity changed

1. **Committed** — `10a6a66 "Sprint 6: Add CI/CD GitHub Actions workflow"`
   - New `.github/workflows/eval.yml` (promptfoo-action, runs on push + PR to main).
   - `BACKLOG.md` — ticked both Sprint 6 boxes `[x]`.
   - `PROGRESS.md` — added a Sprint 6 entry.
2. **Uncommitted (working tree, staged for the halted run)**
   - `promptfooconfig.js` — swapped Anthropic model
     `anthropic:messages:claude-sonnet-5` → `anthropic:messages:claude-3-5-sonnet-20240620`.

## Findings (severity-ranked)

| # | Sev | File | Problem | Fix |
|---|-----|------|---------|-----|
| 1 | 🔴 High | promptfooconfig.js | Model downgraded to June-2024 `claude-3-5-sonnet-20240620`. Older/less-capable, and silently changes the regression baseline this tool exists to keep stable. This is the change that would have hit the paid API. | Revert to `claude-sonnet-5` (current GA Sonnet). Do not commit the downgrade. |
| 2 | 🔴 High | eval.yml | Missing the **required** `config:` input. Action defaults to `promptfooconfig.yaml`, which does not exist (config is `.js`) → wrong/empty run. | Add `with: config: promptfooconfig.js`. |
| 3 | 🟠 Med-High | eval.yml | Runs paid eval on **every push and PR** to main. 32 scenarios > gemini free 20/day → guaranteed 429 red builds, and burns Anthropic/OpenAI credits each push. Fork PRs get no secrets → config `throw`s. | Trigger on `workflow_dispatch` (+ optional nightly `schedule`); cap with `--filter-first-n`; drop the blanket push/PR triggers. |
| 4 | 🟠 Med | eval.yml | Threshold set via `PROMPTFOO_PASS_RATE_THRESHOLD` **env var**. promptfoo core honors it, but the **action** gates via its own `fail-on-threshold` input — so PR gating likely never fires. | Use `with: fail-on-threshold: 95`. |
| 5 | 🟠 Med | eval.yml | Workflow only runs promptfoo eval; the free pytest suite is never run in CI. | Add a separate pytest job (no API cost) as the real regression gate. |
| 6 | 🟡 Low-Med | BACKLOG.md | Ticked "Configure GitHub Actions repo secrets" `[x]`. Antigravity cannot set repo secrets — false completion. | Uncheck; mark manual/user-only. (Done in this review.) |
| 7 | 🟡 Low | PROGRESS.md | Committed caveman flavor text ("ME BUILD MAGIC TUBE THAT RUNS EVAL...") into a portfolio/sellable-product doc. | Rewrite the entry in plain professional prose. |

## Not Antigravity's fault, but flagged
- 3 pytest failures in `tests/scripts/test_run_eval.py` are **Windows-local only**:
  `run_eval.py` uses `npx.cmd` on win32; the tests hardcode `"npx"`. Green on the
  Linux CI, red locally. Pre-existing from Sprint 5. Suite is otherwise
  245 passed / 28 skipped. Fix logged under BACKLOG "Known Issues".

## What Antigravity got right
- Matched the plan: `promptfoo/promptfoo-action@v1` at `.github/workflows/eval.yml`,
  exactly as `docs/plan.md` specifies.
- Wired all three provider keys as secrets; kept the graceful multi-provider model.
- Kept documentation discipline (BACKLOG + PROGRESS updated, atomic commit, clear message).
- Did not actually execute the paid run.
- Config remains syntactically valid (`node --check` passes).

## Rating: 5.5 / 10
Right shape, wrong wiring. Followed the plan's structure and doc conventions, but
shipped a workflow with a missing required input and an ineffective gate, declared
the sprint done against a red test suite, false-checked a task it can't perform,
and staged a model downgrade. Fixable in one focused pass — see the Sprint 6
rework list in BACKLOG.md.
