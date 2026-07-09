// Test-only bridge script: invokes prompts/build_prompt.js exactly the way
// promptfoo's external prompt-function contract does (({ vars }) => string),
// so tests/prompts/test_build_prompt.py can exercise the real file via a
// plain subprocess call instead of duplicating its logic in Python.
//
// Usage: node _run_build_prompt.js '<json-encoded vars object>'
// Prints the resulting prompt string to stdout (raw, unquoted) on success;
// on a thrown error (e.g. a missing schema_file), lets the exception
// propagate so the Node process exits non-zero with the error on stderr —
// exactly what a real promptfoo run would see, not a swallowed failure.

const path = require('path');

const buildPrompt = require(path.join(__dirname, '..', '..', 'prompts', 'build_prompt.js'));

const varsArg = process.argv[2];
if (!varsArg) {
  console.error('Usage: node _run_build_prompt.js \'<json-encoded vars object>\'');
  process.exit(2);
}

const vars = JSON.parse(varsArg);
const result = buildPrompt({ vars });
process.stdout.write(result);
