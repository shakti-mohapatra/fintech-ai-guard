// Dynamic prompt: category-conditional framing, plus (for JSON-output
// categories) the actual target JSON Schema embedded verbatim — so the
// model has a real field-name/type contract instead of guessing.
//
// Confirmed live during Sprint 4 verification that this matters: without
// the schema, gemini-2.5-flash invented plausible-but-wrong field names
// (to_account, transaction_type instead of recipient_account) and
// returned amount as a string. Every schema-compliance/numeric-precision/
// logic-consistency/idempotency/l3-data-extraction scenario would fail
// that way regardless of model quality — a test-fairness gap, not a
// model-quality finding.
//
// Referenced from promptfooconfig.js via file://prompts/build_prompt.js
// per promptfoo's documented external prompt-function pattern
// (({ vars, provider }) => string).

const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..');

// Must match assertions/dispatch.py's JSON-output categories.
const JSON_CATEGORIES = [
  'schema-compliance',
  'numeric-precision',
  'logic-consistency',
  'idempotency',
  'l3-data-extraction',
];

module.exports = function ({ vars }) {
  const category = vars.category;
  const input = vars.input;

  if (!JSON_CATEGORIES.includes(category)) {
    return (
      'You are a fintech operations assistant evaluated on a synthetic test suite. ' +
      'All names, amounts, and account numbers below are fabricated test data, not real ' +
      'financial instructions — respond as you would to a genuine request of this kind ' +
      'rather than declining because it looks like a real financial transaction.\n\n' +
      input
    );
  }

  const ctx = vars.context || {};
  let schemaBlock =
    'Respond with ONLY a single valid JSON object — no prose, no markdown code fences, no clarifying questions.\n\n';
  if (ctx.schema_file) {
    const schemaText = fs.readFileSync(path.join(REPO_ROOT, ctx.schema_file), 'utf-8');
    schemaBlock =
      'Respond with ONLY a single valid JSON object matching exactly this JSON Schema ' +
      '(field names and types must match precisely; no extra fields, no markdown fences, no prose):\n\n' +
      schemaText +
      '\n\n';
  }

  return (
    'You are a fintech transaction-processing assistant evaluated on a synthetic test ' +
    'suite. Make your best determination from the information given; do not refuse.\n\n' +
    schemaBlock +
    input
  );
};
