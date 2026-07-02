"""Shared helper for promptfoo assertions that parse JSON model output.

Not a promptfoo assertion itself (no get_assert) — imported by the ones
that need it.
"""

import re

_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def strip_markdown_fences(text: str) -> str:
    """Strip a single leading/trailing ```json ... ``` fence, if present.

    Providers commonly wrap JSON output in a markdown code fence even when
    explicitly instructed not to (confirmed live with gemini-2.5-flash
    during Sprint 4 verification, despite prompts/build_prompt.js saying
    "no markdown fences") — defensive normalization, not prompt-tuning
    whack-a-mole, and provider-agnostic rather than relying on a specific
    provider's JSON-mode config.
    """
    stripped = text.strip()
    match = _FENCE_PATTERN.match(stripped)
    return match.group(1).strip() if match else stripped
