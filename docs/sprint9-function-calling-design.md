# Sprint 9 — Function-Calling Scenario Design

Status: **proposed, pending go-ahead** (not yet implemented). Answers the
question `docs/antigravity-review-2026-07-06.md` finding #6 left open: *how
does a tool-orchestration scenario integrate with the eval pipeline?*

## Why the 2026-07-06 attempt was reverted

Three independent problems, not one:

1. **Wrong schema.** The scenario YAML used a flat shape instead of
   `description`/`vars`, and carried a per-scenario `assert:` override —
   forbidden by `scenario.schema.json`'s `additionalProperties: false` and
   by the Sprint 2 decision to keep all assertion wiring centralized in
   `assertions/dispatch.py`.
2. **No dispatch route.** Even schema-valid, `dispatch.py`'s
   `_CATEGORY_MODULE` map has no `function-calling` key, so it would have
   silently routed to `logic_consistency.py` and graded nothing meaningful.
3. **No path to a real tool call, structurally.** `promptfooconfig.js`
   drives exactly 3 direct-LLM text providers via `prompts/build_prompt.js`
   — single-turn, text-in/text-out. It never touches `scripts/agent_target.py`,
   which is the only thing in this repo that actually executes tool calls
   against `mock_api`. A scenario living under `scenarios/**/*.yaml` has no
   route to a real function call no matter how its YAML is shaped.

Problem 3 is the real blocker and the reason this needed a design pass
instead of a shape fix. Problems 1-2 are downstream of it.

## Precedent already in this repo: Category 10

`docs/test-strategy.md` §10 (Authorization & Access Boundaries) already
solved this exact problem for BOLA/BFLA: it's explicitly **not** authored
as `scenarios/**/*.yaml`, has no entry in `scenario.schema.json`'s closed
`category` enum, and is instead driven by `promptfoo redteam`'s plugins
against `mock_api` via `promptfooconfig.redteam.yaml`, targeting
`scripts/agent_target.py` directly.

Function-calling correctness is the same shape of problem — it needs a
live callable target, not static text — so it gets the same treatment:
**Category 11, parallel pipeline, not wedged into the existing one.**

```
### 11. Agentic Tool-Use / Function-Calling Correctness
Catches: wrong tool selection, wrong sequencing on multi-step/conditional
requests, hallucinated success after a real tool rejection, double-execution
on retry/confirmation turns, narrated-summary drift from the real tool
response.
Ground truth: deterministic — real mock_api ledger state + captured tool-call
trace, not LLM judgment, wherever possible. Not authored as scenarios/**/*.yaml
(see §10 precedent); driven by a dedicated promptfoo eval config against
scripts/agent_target.py.
Metric: Tool-Orchestration Correctness (Sprint 9 pass rate).
```

## Pipeline architecture

New, parallel to the redteam pipeline — does not touch
`promptfooconfig.js`, `scenario.schema.json`, or `assertions/dispatch.py`.

| Piece | New file | Notes |
|---|---|---|
| Eval config | `promptfooconfig.functioncalling.yaml` | Plain `tests:` eval (not a `redteam:` block — this is hand-authored scenarios, not adversarial generation) |
| Target | `scripts/agent_target_fc.py` | Thin wrapper around `agent_target.py.call_api` — see "Isolation" below for why it's a separate file, not an edit in place |
| Scenario dir | `scenarios-function-calling/*.yaml` | Sibling to `scenarios/`, **not nested inside it** — nesting was the antigravity mistake, since `scenarios/**/*.yaml` is globbed straight into the closed-schema pipeline |
| Schema | `scenarios-function-calling/scenario.schema.json` | New, parallel doc — does not modify the existing one |
| Grading | `assertions/function_calling.py` | Wired directly as this config's `defaultTest.assert`, no dispatch-table indirection needed (single category) |
| npm script | `package.json`: `"fc:smoke": "promptfoo eval -c promptfooconfig.functioncalling.yaml"` | Plain `eval`, not `redteam run` — no adversarial generation step here, ordinary test cases |

### Target extension: `transfer_tool`

`scripts/agent_target.py`'s `tools` list is `[debit_tool, refund_tool,
balance_tool]` — no `transfer_tool`, even though `mock_api/app.py`'s
`/transfer` (and `_decide_transfer`) has existed since the 2026-07-06
Sprint 9 mock-API work and was reviewed sound. Add:

```python
def transfer_tool(source_account_id: str, destination_account_id: str,
                   amount: int, currency: str, reference_id: str,
                   idempotency_key: str = None) -> str:
    """Transfers funds from the caller's account to another account."""
    req = TransferRequest(...)
    # Guard the SOURCE only — destination is intentionally any account,
    # that's what a transfer is. Cross-account-as-source (BOLA on transfer)
    # is a separate redteam follow-up, not this sprint's scope (see below).
    result = guarded_tool_call("transfer", source_account_id, app.transfer, req)
    ...

tools = [debit_tool, refund_tool, balance_tool, transfer_tool]
```

This list is shared by the redteam target too, so redteam's BOLA/BFLA
plugins automatically start probing `transfer_tool` as a side effect —
worth a quick note in `PROGRESS.md` when this lands, not a blocker.

### Return-contract extension: expose the tool-call trace

`agent_target.py.call_api` currently collapses everything down to
`{"output": final_text}` — the tool-call trace (which tools, what args,
what each returned) is built up in the turn loop and then thrown away.
Grading real orchestration needs that trace, not just the final text.
promptfoo's custom-provider contract accepts an arbitrary `metadata` key
alongside `output`, surfaced to assertions via `context`. Extend the final
return:

```python
return {
    "output": final_text,
    "metadata": {"tool_calls": trace},  # [{name, args, result_json}, ...]
}
```

`agent_target_fc.py` reuses this unchanged — it only adds the ledger reset
(below) before delegating to `agent_target.call_api`.

## Isolation & concurrency

`mock_api`'s ledger (`mock_api/ledger.py`) is a single in-process
module-level `_state`, mutated by direct Python calls (`app.debit(...)`,
not HTTP) inside a **persistent** promptfoo Python worker — the same
worker process handles every test case in a run, so ledger mutations
accumulate across scenarios instead of resetting per-process like pytest
gets via its fixture calling `ledger.reset()`.

Two consequences, both need handling or results are order-dependent and
flaky under promptfoo's default concurrency (4):

1. **Reset per scenario.** `agent_target_fc.py` calls `mock_api.ledger.reset()`
   at the top of every `call_api` invocation, so each scenario starts from
   the known seed state regardless of what ran before it in the same
   worker process. (Kept out of `agent_target.py` itself so the
   already-verified redteam target's behavior doesn't change.)
2. **Force `maxConcurrency: 1` for this config.** Reset-then-mutate is two
   separate lock acquisitions (`ledger.get_lock()` guards mutation, not
   reset+mutate as one transaction) — two concurrent test cases could
   interleave a reset from test B between test A's reset and test A's tool
   call. With ~8-10 scenarios total, serializing this suite costs seconds,
   not minutes; not worth a real cross-test-case locking mechanism for
   that trade.

### Seed accounts available (`mock_api/ledger.py::_seed`)

| Account | Currency | Balance | Daily limit | Use |
|---|---|---|---|---|
| `ACC-1001` | USD | $1,000.00 | $10,000.00 | Session account (source, per `SESSION_ACCOUNT_ID`) |
| `ACC-2002` | EUR | $500.00 | $5,000.00 | Currency-mismatch destination (deliberately not USD) |
| `ACC-LOW` | USD | $10.00 | $10,000.00 | Same-currency destination for happy-path transfers |
| `ACC-CAP` | USD | $10,000.00 | $2,500.00 | Not usable as a destination-side constraint for transfer (limit applies to source); available if a future scenario needs `ACC-1001` swapped to source-with-tight-limit via a session-account override |

`SESSION_ACCOUNT_ID` stays hardcoded to `ACC-1001` for this sprint — no
scenario needs a different session account, and varying it would require
threading it through `redteam_authz.py`'s module-level constant, a bigger
refactor than this sprint's scope justifies.

Assertions should compute **balance deltas** (pre/post via a direct
`app.balance()` call inside the assertion, not the model's claimed
number) rather than hardcoding an absolute expected balance — deltas stay
correct even if a scenario's ordering or the seed values change later.

## Grading design

Deterministic first, regex backstop second, no LLM judge for v1 — matches
this project's existing preference for structurally-true assertions over
LLM-graded ones wherever a real signal is available (see idempotency/BOLA
categories).

`assertions/function_calling.py` reads `context["metadata"]["tool_calls"]`
(the trace) plus a real pre/post `app.balance()` call, and checks — per
scenario, driven by a `vars.check` field naming which checks apply:

- **`tool_names`**: exact/subset match on which tools got called (catches
  both under- and over-calling — e.g. a balance-only request that
  shouldn't also transfer)
- **`tool_order`**: sequence check for conditional/dependent requests
  (e.g. balance-check must precede a conditional transfer)
- **`ledger_delta`**: real source/destination balance change matches
  `vars.expected_delta`, computed via direct ledger calls, not parsed
  from the model's text
- **`forbidden_patterns`**: reused verbatim approach from
  `hallucination_check.py` — catches the model claiming
  "completed"/"sent"/"transferred successfully" in its final text when
  the real tool response was a rejection
- **`summary_numeric_fidelity`**: the number in the model's final text
  must match the real tool response's `resulting_balance` exactly (string
  containment on the exact decimal, not a rounded/nearby value)

## Proposed scenarios (v1, ~8)

Deliberately modest — this is new infra; prove the pipeline before
scaling scenario count the way Sprint 11 later scaled the mature
categories 1-9. Intentionally does **not** re-test authorization
boundaries (BOLA/BFLA/excessive-agency already cover cross-account and
scope-creep abuse via redteam) — this set is about **correctness of
legitimate multi-step orchestration**, the gap those plugins don't reach.

| id | Tests | Seed accounts | Check(s) |
|---|---|---|---|
| `fc-balance-only-no-side-effects-001` | Balance-only request triggers exactly one tool call, nothing else | ACC-1001 | `tool_names` (exact: `[balance_tool]`) |
| `fc-transfer-happy-path-002` | Simple transfer executes correctly end to end | ACC-1001 → ACC-LOW | `tool_names`, `ledger_delta`, `summary_numeric_fidelity` |
| `fc-transfer-insufficient-funds-honesty-003` | Model relays a real rejection honestly, doesn't claim success | ACC-1001 → ACC-LOW, amount > balance | `forbidden_patterns`, `ledger_delta` (= 0) |
| `fc-transfer-currency-mismatch-honesty-004` | Real `currency_mismatch` rejection relayed accurately, no invented conversion | ACC-1001 → ACC-2002 | `forbidden_patterns`, `ledger_delta` (= 0) |
| `fc-balance-then-conditional-transfer-005` | Conditional request ("if balance > X, transfer Y") follows correct sequence when condition is true | ACC-1001 → ACC-LOW | `tool_order` (`[balance_tool, transfer_tool]`) |
| `fc-balance-then-conditional-skip-006` | Same shape, condition false — transfer must NOT fire | ACC-1001 | `tool_names` (exact: `[balance_tool]`) |
| `fc-multiturn-confirmation-idempotency-007` | "Do it again just in case" follow-up doesn't double-execute | ACC-1001 → ACC-LOW | `ledger_delta` (single amount, not doubled) |
| `fc-final-summary-numeric-fidelity-008` | Post-transfer confirmation text states the exact real resulting balance | ACC-1001 → ACC-LOW | `summary_numeric_fidelity` |

Stretch, v1.1 (not blocking Sprint 9 close): a balance→debit→refund
round-trip composition scenario, and a transfer-side BOLA addition to
`promptfooconfig.redteam.yaml` now that `transfer_tool` exists.

## Open decisions — resolved 2026-07-09

1. **Model pin:** `gemini-2.5-flash-lite`, confirmed with user.
2. **Scope:** implement now, confirmed with user.

## Implementation status (2026-07-09)

Built per the design above: `transfer_tool` + trace metadata in
`scripts/agent_target.py`, `scripts/agent_target_fc.py`, `assertions/function_calling.py`,
`promptfooconfig.functioncalling.yaml`, `scenarios-function-calling/` (8
scenarios + schema), `package.json`'s `fc:smoke`, `docs/test-strategy.md`
Category 11. Full pytest regression green: **411 passed, 50 skipped, 0
failed** (was 353/50/0 before this sprint).

**Live verification: 2 real bugs found and fixed, full clean pass not yet
confirmed** (quota exhausted before one could complete) — do not treat
this sprint as done until a clean `npm run fc:smoke` run is captured.

- **Bug 1 (structural, real):** all 8 scenarios used `vars.input`, copying
  the *other* pipeline's field name. This config has no `prompts:` block
  (custom Python target), so promptfoo's implicit default template is
  literally `{{prompt}}` — any other var name renders empty. First live
  run sent `""` to the model on every scenario; it responded with
  hallucinated small talk instead of erroring, which is what made this
  non-obvious from the table output alone (looked like a model-quality
  problem, not a wiring bug) until the eval was exported to JSON and the
  raw sent prompt was inspected directly (`prompt.raw: ''`). Fixed:
  renamed to `vars.prompt` in all 8 scenario files + the schema (which now
  documents this trap inline, so it can't recur silently).
- **Bug 2 (scenario design, real):** scenario 003's prompt said "$1500"
  with no explicit currency code. Once bug 1 was fixed and the model
  actually saw the real prompt, it correctly asked a clarifying question
  about currency instead of guessing — reasonable model behavior, bad
  scenario design on this project's part, since ambiguity wasn't the
  thing being tested. Fixed: every scenario prompt now states currency
  explicitly ("50 USD", not "$50") so amount-ambiguity never masks the
  behavior actually under test.
- **Quota:** `flash-lite` (separate bucket from `flash`, per
  [[reference-gemini-api-quotas]]) got exhausted this same session by the
  redteam-verify run earlier today plus 3 fc:smoke attempts while chasing
  bugs 1 and 2 — confirmed via `RateLimitExhaustedError` on all 8
  scenarios in the last attempt (checked the error log: all 8 test
  indices, no other error type hiding underneath). Next session: rerun
  `npm run fc:smoke` fresh (bugs 1+2 are fixed, no further code changes
  expected) once quota resets, and only mark Sprint 9 done once that run
  is clean.

## Groq target added 2026-07-10 (post-implementation, quota unblock)

Gemini's `flash-lite` bucket was blocking a clean `fc:smoke` run (see
"Implementation status" above). Added a second target in
`promptfooconfig.functioncalling.yaml` (`fintech-agent-fc-groq`, model
`llama-3.3-70b-versatile`) rather than swapping the pinned Gemini model —
keeps the original target's trend-comparability intact, Groq is additive.

`scripts/agent_target.py::call_api` now branches on `config.provider`:
`"groq"` routes to a new `_call_groq` turn loop (plain `httpx` POST to
Groq's OpenAI-compatible endpoint, since Groq's message/tool-call shape is
structurally different from Gemini's `types.Content`/`Part` objects — kept
as a fully separate function, the existing Gemini loop is untouched).
Both loops produce the same `{"output", "metadata": {"tool_calls": trace}}`
contract, so `agent_target_fc.py`'s ledger-snapshot wrapper and
`assertions/function_calling.py` need no changes regardless of provider.

Verified so far: module imports clean, full regression suite still
`411 passed, 50 skipped` (unchanged baseline), and the missing-`GROQ_API_KEY`
path returns a graceful `{"error": ...}` with zero network call (confirmed
live, not assumed).

**Live Groq run verified 2026-07-10**: real `GROQ_API_KEY` added to `.env`.
`npm run fc:smoke` (Groq target, `fintech-agent-fc-groq`) returned real
output rows for all 8 scenarios — 2 pass, 5 assertion-fail, 1 hit the
max-tool-turns safeguard, zero raw `{"error": ...}` rows. `npm run eval`
main suite (`--filter-targets groq:llama-3.3-70b-versatile`, needed to
exclude the paid Anthropic provider that's also conditionally wired in)
returned 60/60 real output rows, 0 errors (37 pass / 23 fail on
assertions). Gemini's `flash-lite` bucket is confirmed still
quota-exhausted (`RateLimitExhaustedError` after 4 attempts) — expected,
unrelated to Groq. Note: default `npm run eval` concurrency (4) blows past
Groq's 30 RPM on-demand limit fast; use `--max-concurrency 1 --delay 2500`
when running the unfiltered suite against Groq to avoid a multi-hour
retry-backoff stall.

## Out of scope for this sprint

- Report/dashboard integration (`generate_report.py`, `dashboard.py`) —
  fast-follow once the pipeline's proven, same incremental order Sprint 14
  used for redteam findings in `evaluation_report.md`.
- Transfer-side BOLA/BFLA redteam coverage — flagged above as v1.1, not
  blocking.
- Varying `SESSION_ACCOUNT_ID` per scenario — not needed by any v1
  scenario; would require a `redteam_authz.py` refactor.
