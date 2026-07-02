import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "assertions"))

from _json_utils import strip_markdown_fences  # noqa: E402


def test_strips_json_fence():
    text = '```json\n{"a": 1}\n```'
    assert strip_markdown_fences(text) == '{"a": 1}'


def test_strips_bare_fence_no_language_tag():
    text = '```\n{"a": 1}\n```'
    assert strip_markdown_fences(text) == '{"a": 1}'


def test_leaves_unfenced_json_unchanged():
    text = '{"a": 1}'
    assert strip_markdown_fences(text) == '{"a": 1}'


def test_strips_surrounding_whitespace_around_fence():
    text = '  \n```json\n{"a": 1}\n```\n  '
    assert strip_markdown_fences(text) == '{"a": 1}'


def test_leaves_non_json_text_unchanged():
    text = "I cannot process this request."
    assert strip_markdown_fences(text) == text
