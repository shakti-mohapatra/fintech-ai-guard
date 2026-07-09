import pytest
import json
import tempfile
import sys
from pathlib import Path

# Ensure the scripts directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.generate_redteam_report import compute_redteam_metrics, append_to_report, parse_authz_log

@pytest.fixture
def mock_export():
    return {
        "results": [
            {"success": True, "vars": {"pluginId": "prompt-injection"}},
            {"success": False, "vars": {"pluginId": "prompt-injection"}},
            {"success": True, "vars": {"pluginId": "bola"}},
        ]
    }

@pytest.fixture
def mock_authz_log():
    lines = [
        '{"event": "other_event"}',
        '{"event": "authorization_violation_attempt", "tool_name": "debit", "requested_account_id": "ACC-2002"}',
        'invalid json',
        '{"event": "authorization_violation_attempt", "tool_name": "refund", "requested_account_id": "ACC-LOW"}'
    ]
    return "\n".join(lines)

def test_compute_redteam_metrics(mock_export):
    metrics = compute_redteam_metrics(mock_export, authz_blocks=2)
    assert metrics["authz_blocks"] == 2
    
    plugins = metrics["plugins"]
    assert "prompt-injection" in plugins
    assert plugins["prompt-injection"]["total"] == 2
    assert plugins["prompt-injection"]["passed"] == 1
    assert plugins["prompt-injection"]["failed"] == 1
    
    assert "bola" in plugins
    assert plugins["bola"]["total"] == 1
    assert plugins["bola"]["passed"] == 1

def test_parse_authz_log(mock_authz_log):
    with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f:
        f.write(mock_authz_log)
        f_path = Path(f.name)
        
    try:
        blocks = parse_authz_log(f_path)
        assert blocks == 2
    finally:
        f_path.unlink()

def test_append_to_report(mock_export):
    metrics = compute_redteam_metrics(mock_export, authz_blocks=0)
    
    with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f:
        f.write("# Evaluation Report\n")
        f_path = Path(f.name)
        
    try:
        append_to_report(metrics, f_path)
        content = f_path.read_text(encoding="utf-8")
        
        assert "## Red-Team Findings" in content
        assert "| `prompt-injection` | 2 | 1 | 1 | - |" in content
        # Check for mismatch warning since BOLA passed but blocks = 0
        assert "| `bola` | 1 | 1 | 0 | 0 ⚠️ (Mismatch: Promptfoo passed but 0 blocks logged) |" in content
    finally:
        f_path.unlink()

def test_append_to_report_replaces_prior_section_not_duplicates(mock_export):
    """Regenerating the report (e.g. re-running a redteam suite) must replace
    the old Red-Team Findings section, not stack a second stale one under it."""
    metrics = compute_redteam_metrics(mock_export, authz_blocks=0)

    with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f:
        f.write("# Evaluation Report\n\n## Other Section\n\nkeep me\n")
        f_path = Path(f.name)

    try:
        append_to_report(metrics, f_path)
        append_to_report(metrics, f_path)
        content = f_path.read_text(encoding="utf-8")

        assert content.count("## Red-Team Findings") == 1
        assert "## Other Section" in content
        assert "keep me" in content
    finally:
        f_path.unlink()
