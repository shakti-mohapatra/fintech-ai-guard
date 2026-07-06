// Fintech-AI-Guard main eval config.
//
// JS, not YAML, so `providers` can be built conditionally from whichever
// key(s) are actually present in .env — this is the real mechanism behind
// docs/plan.md's "multi-provider from the start... degrading gracefully"
// design decision. A static YAML providers: list can't omit an entry based
// on an env var, and listing a provider whose key is missing risks a hard
// pre-flight failure that aborts the whole eval rather than just that
// provider's rows. Node's process.env sees .env because promptfoo loads it
// before evaluating this file (same auto-load already proven by the
// Sprint 0 smoke config).
//
// See promptfooconfig.smoke.yaml for the Sprint 0 plumbing check (no API
// key required, kept separate on purpose).

const CANDIDATE_PROVIDERS = [
  {
    envKey: 'ANTHROPIC_API_KEY',
    id: 'anthropic:messages:claude-sonnet-5',
  },
  {
    envKey: 'OPENAI_API_KEY',
    // UNVERIFIED: no OpenAI key has existed yet to test this provider id
    // against a live account. Confirm/replace the model string the first
    // time OPENAI_API_KEY is actually set (see PROGRESS.md).
    id: 'openai:chat:gpt-5.5',
  },
  {
    envKey: 'GOOGLE_API_KEY',
    // Pinned to the stable GA release, not a "-preview" or "-latest" alias
    // — this tool's whole point is trend-comparable regression reports, so
    // the same provider id must mean the same model across eval runs.
    // NOTE: gemini-2.5-pro has a hard 0-quota free tier (requires billing
    // — confirmed live via a direct API call, not just docs). flash is
    // the tier that's actually usable on a free-tier key; revisit if
    // billing gets enabled later.
    id: 'google:gemini-2.5-flash',
  },
];

const providers = CANDIDATE_PROVIDERS.filter((p) => !!process.env[p.envKey]).map((p) => p.id);

if (providers.length === 0) {
  throw new Error(
    'No provider API key found (ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY). ' +
      'Add at least one to .env before running promptfoo eval.',
  );
}

module.exports = {
  description: 'Fintech-AI-Guard evaluation suite',
  // A bare `{{input}}` prompt works with the Sprint 0 `echo` provider (it
  // just parrots the input back) but a real model has no reason to guess
  // that a JSON object is expected, let alone its exact field names — or
  // that refusing is the wrong move for a synthetic test scenario.
  // Confirmed live: gemini-2.5-flash both refused a bare transfer
  // instruction ("I cannot directly transfer money...") AND, once told to
  // respond in JSON without being shown the schema, invented plausible-
  // but-wrong field names (to_account, transaction_type) and returned
  // amount as a string. prompts/build_prompt.js fixes both: category-
  // conditional framing, and the real JSON Schema embedded for JSON
  // categories. See that file for the rationale in full.
  prompts: ['file://prompts/build_prompt.js'],
  providers,
  tests: ['file://scenarios/**/*.yaml'],
  defaultTest: {
    options: {
      // required_fields / forbidden_patterns are YAML arrays in every
      // scenario file; promptfoo's default behavior is to cartesian-expand
      // any array-valued var into one test case per element (confirmed
      // live: a single scenario with a 3-item required_fields silently
      // became 3 test cases). We want those arrays passed through whole
      // to assertions/dispatch.py, not expanded.
      disableVarExpansion: true,
    },
    assert: [
      {
        type: 'python',
        value: 'file://assertions/dispatch.py',
      },
    ],
  },
};
