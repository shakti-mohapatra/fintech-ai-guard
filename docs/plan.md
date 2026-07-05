# Project Plan — Fintech-AI-Guard

> Portable copy of the original design plan, kept in-repo so any AI coding
> tool (not just the one that wrote it) can resume this project cold. For
> live day-to-day status, read `PROGRESS.md` first, then `BACKLOG.md`.

> [!WARNING]
> **Synthetic Data Disclaimer:** All data in this project is 100% synthetic and fabricated. We use published Luhn-valid test ranges only. No real PCI-scope data or PII is ever used or stored in this repository.

## Objective

Fintech-AI-Guard is **not a chatbot or a product feature** — it's a **validation/evaluation engine** that answers one question repeatably: *"If we swap in LLM X for this fintech workflow, does it reliably stay inside our compliance and business-logic contract — under normal conditions and under adversarial ones — and can we prove it on every change?"*

Three layers:
1. **Scenario Factory** (input layer): hand-authored edge cases as YAML — boundary cases (over-limit transfers, malformed card data), adversarial cases (prompt injection hidden in a transaction memo or an invoice being parsed), and logic-trap cases (refund vs. debit confusion).
2. **Execution Engine**: `promptfoo` runs each scenario against one or more LLMs, capturing both free-text and structured/tool-call output.
3. **Validation Layer**: custom Python assertions grade every output against schema, PII/PCI-leakage, numeric-precision, business-logic, and tone/compliance rules.

Output: a versioned, CI-gated `evaluation_report.md` with concrete QA metrics — regression testing, but for AI behavior instead of code behavior. It doubles as a demoable product: something a prospective client can be shown live, not just a static repo.

**Positioning:** both a public GitHub portfolio piece (repositioning for "GenAI Quality Architect" / AI-adjacent QA roles) and a product intended to be demoed and sold to clients. Production-readiness is a real requirement (real error handling, retries, structured logging, secrets hygiene) on free-tier infra for now, swappable to client accounts later. **All scenario data is synthetic/fabricated — no real account numbers, no real PCI-scope data, ever.**

## Architecture decisions (and why)

- **L3 payment-data extraction, not raw ISO 8583.** ISO 8583 is a low-level binary interbank authorization-switching protocol — not something an LLM would realistically emit as JSON. L3 (Level 3) line-item invoice/PO extraction (tax amount, commodity code, PO number, freight/duty) is more realistic and equally domain-credible. Raw ISO 8583 stays as an optional advanced scenario later, not the MVP backbone.
- **promptfoo is the execution engine** — Node.js/npm CLI, YAML config, even though assertions/reports are Python (dual-runtime by design). Custom Python assertions use `type: python`; an external `.py` file defines `get_assert(output, context) -> bool | float | GradingResult`. **Assertion file paths resolve relative to the config file's directory, not CWD.**
- **`tests: file://scenarios/**/*.yaml`** is the standard externalized-scenario pattern. Known gotcha: [promptfoo issue #5696](https://github.com/promptfoo/promptfoo/issues/5696) — var-glob-expansion bug on externally referenced files; low risk here since scenarios are hand-authored, not var-templated.
- **CI gating via `PROMPTFOO_PASS_RATE_THRESHOLD`** (native, exits 100 on breach) — custom scripts (`scripts/generate_report.py`) stay pure reporting, not gating logic.
- **CI built around `promptfoo/promptfoo-action@v1`** — auto-posts a pass/fail PR comment with a viewer link, more idiomatic than hand-rolled shell steps.
- **BOLA/BFLA redteam plugins need a real callable target.** promptfoo's built-in `redteam` module's authorization-bypass plugins are built for agentic/tool-calling targets — against a plain text target there's no real authorization boundary to probe. The "refund shouldn't trigger debit" automation story specifically needs the `mock_api/` stub to exist first; redteam's other plugins (injection, jailbreak, PII leakage, excessive agency) work standalone with no such dependency.
- **Multi-provider from the start** (Claude Sonnet 5 / Opus 4.8, GPT-5.5, Gemini 3.1 Pro — whichever API keys are available, degrading gracefully), kept in exactly one place (`promptfooconfig.yaml`'s `providers:` block) since model names churn fast.

## Working process

- **Sprint-based backlog, 1:1 with GitHub Milestones.** Every task is a GitHub Issue, title matching its `BACKLOG.md` line verbatim (required for Mission Control's GitHub sync to merge instead of duplicate — see that project's own docs if working from this machine). Full backlog seeded up front (Sprint 1); `BACKLOG.md` stays "agile & living" from there.
- **Task lifecycle:** label an issue `in-progress` when starting it → on completion, tick the `BACKLOG.md` checkbox, close the GitHub issue, add a `PROGRESS.md` entry. Status updates can batch at sprint boundaries rather than after every single task.
- **Bugs found during testing** get filed as GitHub issues labeled `bug`, not generic tasks.
- **Unit tests (pytest, `tests/`) run after every meaningful implementation chunk automatically** — a standing behavior, not something to ask for each time.
- **Three testing tiers:** *Smoke* (trivial end-to-end plumbing check, re-run after any environment/config change) · *Sanity* (fast subset, 1-2 scenarios per risk category, after any scenario/assertion change) · *Regression* (full suite vs. last recorded baseline in `reports/`, at sprint end + before every push).
- **State lives in files, not chat.** `BACKLOG.md`, `PROGRESS.md`, `docs/`, commit history, GitHub Issues — so any AI coding tool can resume cold, not just the one that started the project.

## Repo structure

```
fintech-ai-guard/
├── .github/workflows/eval.yml       # uses promptfoo/promptfoo-action@v1
├── docs/
│   ├── plan.md                      # this file
│   ├── architecture.md
│   ├── test-strategy.md             # risk taxonomy, ground-truth methodology, coverage matrix
│   ├── compliance-mapping.md        # assertion -> PCI-DSS / regulatory clause mapping
│   └── metrics.md                   # every QA metric, incl. consistency methodology
├── scenarios/
│   ├── schema/
│   ├── hallucination/*.yaml
│   ├── injection/{direct,document-embedded}/*.yaml
│   ├── schema-compliance/*.yaml
│   ├── numeric-precision/*.yaml
│   ├── logic-consistency/*.yaml
│   ├── idempotency/*.yaml
│   ├── pii-pci/*.yaml
│   ├── l3-data-extraction/*.yaml
│   └── tone-disclosure/*.yaml
├── assertions/                      # Python, wired via promptfoo's `type: python`
├── tests/                           # pytest — unit-tests the assertion CODE (meta-QA)
├── mock_api/                        # FastAPI stub: POST /debit, /refund, /balance
├── scripts/                         # run_eval.py, generate_report.py (pure reporting)
├── reports/                         # curated historical snapshots (timestamp + git sha + model)
├── logs/                            # structured audit trail, with reason codes
├── promptfooconfig.yaml
├── BACKLOG.md                       # Mission Control format — sprints/tasks, mirrors GitHub Issues
├── PROGRESS.md                      # Mission Control format — running log, newest first, READ FIRST
└── evaluation_report.md             # auto-regenerated copy of latest reports/*.md
```

## Risk taxonomy (10 categories)

1. **Hallucination** — fabricated amounts, dates, account numbers, entities not present in source input.
2. **Prompt Injection** — direct (chat input) and document-embedded (malicious text inside an invoice/PO being extracted).
3. **Schema & Data-Type Compliance** — structured output matches its JSON Schema contract.
4. **Numeric & Currency Precision** — decimal/float handling on tax splits, multi-currency conversion, rounding. *The classic fintech bug class.*
5. **Business-Logic Consistency** — refund never calls debit, daily-limit enforcement, zero/negative amounts, Luhn-valid-but-wrong-BIN cards.
6. **Idempotency / Duplicate-Transaction Handling** — same instruction submitted twice: flagged, or blindly processed twice?
7. **PII / PCI Data Handling** — masked PAN, no CVV echo/storage, no full account numbers in plaintext.
8. **L3 / Document Extraction Accuracy** — invoice/PO line-item math, tax reconciliation, commodity codes, PO numbers.
9. **Tone, Disclosure & Regulatory Language** — professional tone, required disclosures, no unauthorized financial advice.
10. **Authorization & Access Boundaries** — BFLA/BOLA-style checks via promptfoo redteam against the mock API (needs the mock stub — Sprint 8).

## QA Metrics

| Metric | What it catches |
|---|---|
| Schema Validation Pass Rate | Malformed/non-conforming structured output |
| Hallucination Rate | Fabricated financial facts |
| Numeric Precision Error Rate | Float/rounding errors in currency math |
| PII/PCI Leakage Rate | Unmasked sensitive data in output |
| Prompt-Injection Resistance Rate | Direct vs. document-embedded, tracked separately |
| Business-Logic Consistency Rate | Wrong action selected (refund→debit, etc.) |
| Idempotency Handling Rate | Duplicate submissions correctly flagged |
| Authorization-Boundary Integrity | BFLA/BOLA cross-account violations (Sprint 8, needs mock API) |
| False-Refusal / Over-Blocking Rate | Legitimate requests wrongly denied |
| Tone & Disclosure Compliance Score | LLM-rubric-graded professionalism/required language |
| Explainability / Reason-Code Completeness | Does a rejection/flag come with a *why* |
| Cross-Run Consistency | Determinism (temp=0) vs. semantic consistency (sampled-N) — two distinct sub-metrics |
| Latency (p50/p95) | Response time |
| **Composite Compliance Pass Rate** | Aggregate headline number for the README |

## Sprint list

**MVP — Sprints 0-7:** 0 Foundation & Environment · 1 GitHub + Mission Control Wiring · 2 Risk Taxonomy & Ground-Truth Schema · 3 Scenario + Assertion Authoring (interleaved per category, incl. the minimal `mock_api` stub) · 4 promptfoo Wiring · 5 Reporting & Metrics · 6 CI/CD · 7 Documentation Polish.

**Day 2 / Stretch — Sprints 8-10:** 8 Red-Teaming (highest-leverage next step, not pure stretch) · 9 Full Agentic Mock-API Buildout · 10 Trend Dashboard.

Full per-task breakdown lives in `BACKLOG.md`, kept current there rather than duplicated here.

## Verification checklist

- `pytest tests/` passes
- `promptfoo eval` runs clean (smoke config needs no API key — uses the `echo` provider; the real config needs at least one provider key in `.env`)
- `scripts/generate_report.py` produces a valid `evaluation_report.md` with real numbers, not placeholders
- GitHub Milestones/Issues match `BACKLOG.md` 1:1
- GitHub Actions workflow succeeds on a test PR and posts a PR comment
