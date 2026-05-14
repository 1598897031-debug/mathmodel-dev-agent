#!/usr/bin/env python3
"""
MathModel Dev Agent - Unified CLI Entry Point

Usage:
    python main.py solve <problem_file> [--project-name NAME] [--verbose] [--debug] [--skills]
    python main.py list
    python main.py info <project_dir>
    python main.py sync [--yes] [--message MSG]
    python main.py <problem_file>              # backward compat alias for solve
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

BANNER = r"""
  __  __           _     _                    _____    _
 |  \/  | ___   __| | __| | ___  _ __ ___   |  ___|__| |__   ___  _ __   __ _  ___ _ __
 | |\/| |/ _ \ / _` |/ _` |/ _ \| '_ ` _ \  | |_ / _ \ '_ \ / _ \| '_ \ / _` |/ _ \ '__|
 | |  | | (_) | (_| | (_| | (_) | | | | | | |  _|  __/ |_) | (_) | | | | (_| |  __/ |
 |_|  |_|\___/ \__,_|\__,_|\___/|_| |_| |_| |_|  \___|_.__/ \___/|_| |_|\__, |\___|_|
                                                                          |___/
"""

# Agent labels for display
AGENT_LABELS = {
    "parser": "Problem Parser",
    "strategy": "Modeling Strategy",
    "code": "Code Execution",
    "experiment": "Experiment Analysis",
    "paper": "Paper Writing",
    "github": "GitHub Automation",
}

# Active skills documentation
ACTIVE_SKILLS = {
    "python-debug": "CodeAgent auto-retry loop (max 3 retries on execution failure)",
    "context-engineering": "Orchestrator context compression between agents",
}


def create_output_dir(outputs_dir: Path, project_name: str) -> Path:
    """Create timestamped output directory under outputs/"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{project_name}_{timestamp}"
    output_dir = outputs_dir / dir_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_execution_log(output_dir: Path, result: dict, timing: dict):
    """Write detailed execution log to output directory"""
    log_file = output_dir / "execution.log"
    lines = []
    lines.append("=" * 64)
    lines.append("MathModel Dev Agent - Execution Log")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 64)

    # Status
    status_str = "SUCCESS" if result["success"] else "FAILED"
    lines.append(f"\nStatus: {status_str}")
    lines.append(f"Project: {result['project_dir']}")

    # Agent execution details
    lines.append(f"\n{'Agent':<25} {'Status':<10} {'Time':<10}")
    lines.append("-" * 45)

    from mathmodel.orchestrator import AGENT_LABELS as ORCH_LABELS
    for name in ["parser", "strategy", "code", "experiment", "paper", "github"]:
        label = ORCH_LABELS.get(name, name)
        elapsed = timing.get(name, "-")
        elapsed_str = f"{elapsed}s" if isinstance(elapsed, (int, float)) else str(elapsed)

        if name in result.get("results", {}):
            ok = result["results"][name].success
            status = "[OK]" if ok else "[FAIL]"
            error = result["results"][name].error
        else:
            status = "  --  "
            elapsed_str = "  --"
            error = None

        lines.append(f"  {label:<23} {status:<10} {elapsed_str:<10}")
        if error:
            lines.append(f"    Error: {error[:200]}")

    total = timing.get("total", "-")
    total_str = f"{total}s" if isinstance(total, (int, float)) else str(total)
    lines.append("-" * 45)
    lines.append(f"  {'Total':<23} {'':10} {total_str:<10}")

    # Output files
    summary = result.get("summary", {})
    output_files = summary.get("output_files", {})
    if output_files:
        lines.append(f"\nOutput Files:")
        for key, path in output_files.items():
            if path:
                if isinstance(path, list):
                    for p in path:
                        lines.append(f"  - {p}")
                else:
                    lines.append(f"  - {path}")

    # Active skills
    lines.append(f"\nActive Skills:")
    for skill, desc in ACTIVE_SKILLS.items():
        lines.append(f"  - {skill}: {desc}")

    lines.append("\n" + "=" * 64)
    log_file.write_text("\n".join(lines), encoding="utf-8")
    return log_file


def print_summary(result: dict, timing: dict, show_skills: bool = False):
    """Print pipeline execution summary"""
    print("\n")
    print("=" * 64)
    print("  Pipeline Execution Summary")
    print("=" * 64)

    summary = result.get("summary", {})

    status_str = "[OK] Success" if result["success"] else "[FAIL] Failed"
    print(f"\n  Status:   {status_str}")
    print(f"  Project:  {result['project_dir']}")

    # Agent table
    print(f"\n  {'Agent':<25} {'Status':<10} {'Time':<10}")
    print(f"  {'-' * 45}")

    for name in ["parser", "strategy", "code", "experiment", "paper", "github"]:
        label = AGENT_LABELS.get(name, name)
        elapsed = timing.get(name, "-")
        elapsed_str = f"{elapsed}s" if isinstance(elapsed, (int, float)) else str(elapsed)

        if name in result.get("results", {}):
            ok = result["results"][name].success
            status = "[OK]" if ok else "[FAIL]"
        else:
            status = "  --  "
            elapsed_str = "  --"

        print(f"  {label:<23} {status:<10} {elapsed_str:<10}")

    total = timing.get("total", "-")
    total_str = f"{total}s" if isinstance(total, (int, float)) else str(total)
    print(f"  {'-' * 45}")
    print(f"  {'Total':<23} {'':10} {total_str:<10}")

    # Output files
    output_files = summary.get("output_files", {})
    if output_files:
        print(f"\n  Output Files:")
        for key, path in output_files.items():
            if path:
                if isinstance(path, list):
                    for p in path:
                        print(f"    - {p}")
                else:
                    print(f"    - {path}")

    # Model metrics
    results = result.get("results", {})
    if "experiment" in results and results["experiment"].success:
        metrics = results["experiment"].output.get("metrics", {})
        if metrics:
            print(f"\n  Model Metrics:")
            for key, val in metrics.items():
                print(f"    {key}: {val}")

    # Skills status
    if show_skills:
        print(f"\n  Active Skills:")
        for skill, desc in ACTIVE_SKILLS.items():
            print(f"    - {skill}: {desc}")

    # Output directory
    if result["success"]:
        print(f"\n  All done! Output files:")
        print(f"    Paper:   {result['project_dir']}/paper/paper.md")
        print(f"    Code:    {result['project_dir']}/code/solution.py")
        print(f"    Report:  {result['project_dir']}/experiment_report.md")
        print(f"    README:  {result['project_dir']}/README.md")
    else:
        print(f"\n  Some steps failed. Check execution.log for details.")

    print("=" * 64)


def cmd_solve(args):
    """Execute the full modeling pipeline"""
    from mathmodel.config import AppConfig, load_config
    from mathmodel.orchestrator import Orchestrator

    problem_path = Path(args.problem_file)
    if not problem_path.exists():
        print(f"Error: File not found - {problem_path}")
        sys.exit(1)

    config = load_config()
    config.verbose = args.verbose
    config.debug = args.debug

    # Create output directory
    output_dir = create_output_dir(config.project.outputs_dir, args.project_name)
    config.project.projects_dir = output_dir.parent

    orchestrator = Orchestrator(config)

    print(BANNER)
    print(f"  Problem:  {problem_path}")
    print(f"  Project:  {args.project_name}")
    print(f"  Output:   {output_dir}")
    print("=" * 64)

    try:
        result = orchestrator.execute(
            problem_file=problem_path,
            project_name=args.project_name,
        )

        timing = result.get("timing", {})

        # Print summary
        print_summary(result, timing, show_skills=args.skills)

        # Write execution log
        log_file = write_execution_log(output_dir, result, timing)
        print(f"\n  Execution log: {log_file}")

        sys.exit(0 if result["success"] else 1)

    except Exception as e:
        print(f"\nExecution error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def cmd_list(args):
    """List past solve runs"""
    from mathmodel.config import load_config

    config = load_config()
    outputs_dir = config.project.outputs_dir

    if not outputs_dir.exists():
        print("No runs found. Outputs directory does not exist yet.")
        print(f"  Expected location: {outputs_dir}")
        return

    projects = sorted(outputs_dir.iterdir(), reverse=True)
    projects = [p for p in projects if p.is_dir()]

    if not projects:
        print("No runs found in outputs directory.")
        return

    print(f"\n{'Run':<40} {'Status':<10} {'Time'}")
    print("-" * 70)

    for proj in projects:
        summary_file = proj / "summary.json"
        has_code = (proj / "code" / "solution.py").exists()
        has_paper = (proj / "paper" / "paper.md").exists()
        has_log = (proj / "execution.log").exists()

        if summary_file.exists():
            with open(summary_file, "r", encoding="utf-8") as f:
                summary = json.load(f)
            gen_time = summary.get("generated_at", "")
            time_str = gen_time[:19] if gen_time else "unknown"
        else:
            time_str = datetime.fromtimestamp(proj.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        # Determine status from file artifacts
        if has_code and has_paper:
            status_str = "[OK]"
        elif has_log:
            # Check execution.log for final status
            log_file = proj / "execution.log"
            log_content = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
            status_str = "[OK]" if "SUCCESS" in log_content else "[FAIL]"
        else:
            status_str = "[FAIL]"

        print(f"  {proj.name:<38} {status_str:<10} {time_str}")

    print(f"\n  Total: {len(projects)} run(s)")
    print(f"  Location: {outputs_dir}")


def cmd_info(args):
    """Show details of a specific run"""
    project_dir = Path(args.project_dir)
    if not project_dir.exists():
        print(f"Error: Directory not found - {project_dir}")
        sys.exit(1)

    summary_file = project_dir / "summary.json"
    if not summary_file.exists():
        print(f"Error: No summary.json found in {project_dir}")
        sys.exit(1)

    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)

    print(f"\n{'=' * 60}")
    print(f"  Run Info: {project_dir.name}")
    print(f"{'=' * 60}")

    # Problem info
    problem = summary.get("problem", {})
    print(f"\n  Problem:")
    print(f"    Title:    {problem.get('title', 'N/A')}")
    print(f"    Type:     {problem.get('type', 'N/A')}")
    print(f"    Objective: {problem.get('objective', 'N/A')}")

    # Solution info
    solution = summary.get("solution", {})
    print(f"\n  Solution:")
    print(f"    Approach: {solution.get('approach', 'N/A')}")
    approaches = solution.get("approaches", [])
    if approaches:
        print(f"    Candidates:")
        for a in approaches:
            flag = " [recommended]" if a.get("recommended") else ""
            print(f"      - {a.get('name', 'N/A')}{flag} (complexity: {a.get('complexity', 'N/A')})")

    # Metrics
    metrics = summary.get("metrics", {})
    if metrics:
        print(f"\n  Metrics:")
        for key, value in metrics.items():
            print(f"    {key}: {value}")

    # Files
    files = summary.get("files", {})
    if files:
        print(f"\n  Output Files:")
        for key, path in files.items():
            full_path = project_dir / path
            exists = "[exists]" if full_path.exists() else "[missing]"
            print(f"    {key}: {path} {exists}")

    print(f"\n  Generated: {summary.get('generated_at', 'N/A')}")
    print(f"{'=' * 60}")


def cmd_sync(args):
    """Sync system changes to GitHub: detect, commit, push."""
    from mathmodel.sync import detect_changed_files, classify_changes, generate_summary, sync_push

    files = detect_changed_files()
    classified = classify_changes(files)

    if not files:
        print("No changes detected.")
        return

    # Show summary
    print(generate_summary(files))

    if not classified["system"]:
        print("\nOnly output changes -- nothing to commit.")
        return

    # Auto-prompt for confirmation
    if not args.yes:
        answer = input("\nCommit and push system changes? [Y/n] ").strip().lower()
        if answer and answer != "y":
            print("Aborted.")
            return

    result = sync_push(message=args.message)
    if result["success"]:
        print(f"\n{result['message']}")
        if result["summary"]:
            print(result["summary"])
    else:
        print(f"\nFailed: {result['message']}")
        sys.exit(1)


def cmd_check(args):
    """Check for system-level changes and prompt for sync."""
    from mathmodel.sync import detect_changed_files, classify_changes, generate_summary, sync_push

    files = detect_changed_files()
    if not files:
        return

    classified = classify_changes(files)

    # Only prompt for system-level changes
    if not classified["system"]:
        return

    print("\n" + "=" * 64)
    print("  [auto-sync] System-level changes detected!")
    print("=" * 64)
    print(generate_summary(files))

    answer = input("\nCommit and push now? [Y/n] ").strip().lower()
    if answer and answer != "y":
        print("Skipped. You can sync later with: python main.py sync")
        return

    result = sync_push()
    if result["success"]:
        print(f"\n{result['message']}")
    else:
        print(f"\nSync failed: {result['message']}")


def main():
    """Main entry point with subcommand support"""
    parser = argparse.ArgumentParser(
        description="MathModel Dev Agent - Automated Mathematical Modeling System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py solve examples/sample_optimization.txt
  python main.py solve examples/sample_prediction.txt --project-name forecast
  python main.py list
  python main.py info outputs/mathmodel_20260513_153831
  python main.py sync                    # commit & push system changes
  python main.py sync --yes              # skip confirmation
  python main.py examples/sample_optimization.txt   # alias for solve
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- solve subcommand ---
    solve_parser = subparsers.add_parser(
        "solve",
        help="Run the full modeling pipeline on a problem file",
        description="Execute the complete pipeline: Parser -> Strategy -> Code -> Experiment -> Paper",
    )
    solve_parser.add_argument(
        "problem_file",
        help="Path to the problem file (TXT, Markdown, or PDF)",
    )
    solve_parser.add_argument(
        "--project-name", "-n",
        default="mathmodel",
        help="Project name (default: mathmodel)",
    )
    solve_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )
    solve_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (full traceback on errors)",
    )
    solve_parser.add_argument(
        "--skills",
        action="store_true",
        help="Show active skills in summary",
    )

    # --- list subcommand ---
    subparsers.add_parser(
        "list",
        help="List past solve runs",
    )

    # --- info subcommand ---
    info_parser = subparsers.add_parser(
        "info",
        help="Show details of a specific run",
    )
    info_parser.add_argument(
        "project_dir",
        help="Path to the project output directory",
    )

    # --- sync subcommand ---
    sync_parser = subparsers.add_parser(
        "sync",
        help="Commit and push system changes to GitHub",
        description="Detect system-level changes, commit, and push. Output-only changes are ignored.",
    )
    sync_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    sync_parser.add_argument(
        "--message", "-m",
        default=None,
        help="Custom commit message (auto-generated if omitted)",
    )

    # Backward compatibility: if no subcommand keyword, inject "solve"
    if len(sys.argv) > 1 and sys.argv[1] not in ("solve", "list", "info", "sync", "-h", "--help"):
        sys.argv.insert(1, "solve")

    # Parse args
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Dispatch
    if args.command == "solve":
        cmd_solve(args)
        # Auto-check: prompt if system changes detected after solve
        cmd_check(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "info":
        cmd_info(args)
    elif args.command == "sync":
        cmd_sync(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
