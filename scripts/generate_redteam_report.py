import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def parse_authz_log(log_path: Path) -> int:
    """Parses the authz log and returns the number of blocked BOLA/BFLA attempts."""
    if not log_path.exists():
        return 0
    count = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if event.get("event") == "authorization_violation_attempt":
                count += 1
        except json.JSONDecodeError:
            pass
    return count

def compute_redteam_metrics(export: dict, authz_blocks: int = 0) -> dict:
    results = export.get("results", [])
    if isinstance(export.get("results"), dict):
        results = export["results"].get("results", [])
        
    plugins_summary = {}
    
    for r in results:
        v = r.get("vars", {})
        # Redteam output usually has pluginId or similar in vars or grading
        plugin = v.get("pluginId") or r.get("pluginId") or v.get("plugin") or "(unknown plugin)"
        
        bucket = plugins_summary.setdefault(plugin, {"total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        
        if r.get("success"):
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1
            
    return {
        "plugins": plugins_summary,
        "authz_blocks": authz_blocks
    }

def append_to_report(metrics: dict, report_path: Path):
    if not report_path.exists():
        lines = ["# Evaluation Report\n\n"]
    else:
        lines = report_path.read_text(encoding="utf-8").splitlines()
        
    lines.append("")
    lines.append("## Red-Team Findings")
    lines.append("")
    lines.append("| Plugin | Tests | Passed | Failed | Structural Blocks (BOLA/BFLA) |")
    lines.append("|---|---|---|---|---|")
    
    for plugin, stats in metrics["plugins"].items():
        structural = "-"
        if plugin in ["bola", "bfla"]:
            structural = str(metrics["authz_blocks"])
            if stats["passed"] > 0 and metrics["authz_blocks"] == 0:
                structural += " ⚠️ (Mismatch: Promptfoo passed but 0 blocks logged)"
                
        lines.append(f"| `{plugin}` | {stats['total']} | {stats['passed']} | {stats['failed']} | {structural} |")
        
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")

def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Usage: python scripts/generate_redteam_report.py <promptfoo_output.json> [authz_log.jsonl]", file=sys.stderr)
        return 1

    export_path = Path(argv[0])
    export = load_json(export_path)
    
    authz_blocks = 0
    if len(argv) > 1:
        authz_blocks = parse_authz_log(Path(argv[1]))
        
    metrics = compute_redteam_metrics(export, authz_blocks)
    report_path = REPO_ROOT / "evaluation_report.md"
    append_to_report(metrics, report_path)
    print(f"Appended Red-Team Findings to {report_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
