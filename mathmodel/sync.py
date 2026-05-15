"""
GitHub Auto Sync System

Detects system-level changes, auto-commits with timestamped messages,
and pushes to GitHub. Problem outputs (outputs/) are NEVER synced.

Usage:
    from mathmodel.sync import auto_sync, print_sync_report, get_status_report
    python main.py sync [--yes] [--message MSG]
    python main.py status
"""

import subprocess
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────────────────────
# System-level paths that constitute "real" project changes
# ──────────────────────────────────────────────────────────────
SYSTEM_PATHS = {
    "main.py",
    "requirements.txt",
    "README.md",
    "CLAUDE.md",
    "CASE_STUDY.md",
    ".gitignore",
    ".env.example",
    "pyproject.toml",
}

SYSTEM_DIRS = (
    "mathmodel/",
    "examples/",
    "tests/",
    "skills/",
    "problems/",
    "config/",
    "docs/",
)

# Paths / patterns that are NEVER committed
OUTPUT_PATTERNS = (
    "outputs/",
    "projects/",
    "temp/",
    "cache/",
    "tmp/",
    "test_paper_verify",
)

OUTPUT_SUFFIXES = {".log", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg"}

IGNORE_FILES = {
    "mimo token.txt",
    "「",
    ".env",
    ".env.local",
    "execution.log",
    "results.json",
}


# ──────────────────────────────────────────────────────────────
# Git helpers
# ──────────────────────────────────────────────────────────────
def _run_git(args: list[str], cwd: str | Path | None = None) -> tuple[bool, str]:
    """Run a git command and return (success, stdout)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            cwd=cwd,
            timeout=30,
        )
        stdout = result.stdout.decode("utf-8", errors="replace").strip() if result.stdout else ""
        return result.returncode == 0, stdout
    except FileNotFoundError:
        return False, "git not found in PATH"
    except subprocess.TimeoutExpired:
        return False, "git command timed out"


def get_project_root() -> Path:
    """Return the repository root (parent of mathmodel/)."""
    return Path(__file__).resolve().parent.parent


def _get_current_branch(root: Path | None = None) -> str:
    root = root or get_project_root()
    ok, out = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    return out.strip() if ok else "master"


def _get_remote_url(root: Path | None = None) -> str:
    root = root or get_project_root()
    ok, out = _run_git(["remote", "get-url", "origin"], cwd=root)
    return out.strip() if ok else "(no remote)"


def _get_short_hash(root: Path | None = None) -> str:
    root = root or get_project_root()
    ok, out = _run_git(["rev-parse", "--short", "HEAD"], cwd=root)
    return out.strip() if ok else "???????"


# ──────────────────────────────────────────────────────────────
# Change detection
# ──────────────────────────────────────────────────────────────
def detect_changed_files() -> list[str]:
    """Return all changed files (staged + unstaged + untracked)."""
    root = get_project_root()
    ok, output = _run_git(["status", "--porcelain"], cwd=root)
    if not ok:
        return []
    files = []
    for line in output.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            files.append(parts[1])
    return files


def classify_changes(files: list[str]) -> dict[str, list[str]]:
    """
    Classify files into 'system' and 'output' categories.

    Returns:
        {"system": [...], "output": [...]}
    """
    system: list[str] = []
    output: list[str] = []

    for f in files:
        if f in IGNORE_FILES:
            continue

        path = Path(f)

        # Output / temp directories
        if any(f.startswith(p) for p in OUTPUT_PATTERNS):
            output.append(f)
            continue

        # Output file suffixes (images, docs, logs) -- unless inside tracked dirs
        if path.suffix.lower() in OUTPUT_SUFFIXES:
            if not any(f.startswith(d) for d in SYSTEM_DIRS):
                output.append(f)
                continue

        # Explicit system files
        if f in SYSTEM_PATHS:
            system.append(f)
            continue

        # System directories
        if any(f.startswith(d) for d in SYSTEM_DIRS):
            system.append(f)
            continue

        # New files at root level: treat as system
        if len(path.parts) == 1:
            system.append(f)
            continue

        # Default: system
        system.append(f)

    return {"system": system, "output": output}


def has_system_changes(files: list[str] | None = None) -> bool:
    if files is None:
        files = detect_changed_files()
    return len(classify_changes(files)["system"]) > 0


def has_output_only_changes(files: list[str] | None = None) -> bool:
    """True if ALL changes are output-only (should block commit)."""
    if files is None:
        files = detect_changed_files()
    if not files:
        return False
    classified = classify_changes(files)
    return len(classified["system"]) == 0 and len(classified["output"]) > 0


# ──────────────────────────────────────────────────────────────
# Commit message generation
# ──────────────────────────────────────────────────────────────
_SUMMARY_MAP = {
    "paper_agent": "paper-agent-improvement",
    "code_agent": "code-agent-update",
    "strategy_agent": "strategy-agent-update",
    "parser_agent": "parser-agent-update",
    "experiment_agent": "experiment-agent-update",
    "github_agent": "github-agent-update",
    "orchestrator": "orchestrator-update",
    "base": "agent-base-refactor",
    "llm_client": "llm-client-update",
    "document_parser": "doc-parser-update",
    "config": "config-update",
    "sync": "github-sync-fix",
    "main": "cli-update",
    "requirements": "dependency-update",
    "README": "docs-update",
    "CLAUDE": "claude-md-update",
    "pyproject": "build-config-update",
    "test": "test-update",
    "sample": "example-update",
}


def _generate_commit_message(changed_files: list[str]) -> str:
    """Generate a short, descriptive commit message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d")

    stems = {Path(f).stem.lower() for f in changed_files}
    label = "system-update"

    for key, summary in _SUMMARY_MAP.items():
        if any(key in s for s in stems):
            label = summary
            break

    if len(changed_files) > 8:
        label = f"multi-agent-update +{len(changed_files)} files"

    return f"auto-update: {timestamp} {label}"


# ──────────────────────────────────────────────────────────────
# Sync operations
# ──────────────────────────────────────────────────────────────
def sync_push(
    message: str | None = None,
    files: list[str] | None = None,
) -> dict:
    """
    Stage system files, commit, and push.

    Returns:
        {"success": bool, "message": str, "commit": str, "files": list[str]}
    """
    root = get_project_root()

    if files is None:
        files = detect_changed_files()

    classified = classify_changes(files)

    # Safety: block if only output changes
    if not classified["system"]:
        if classified["output"]:
            return {
                "success": True,
                "message": "[Skipped] Only problem outputs changed. GitHub sync ignored.",
                "commit": "",
                "files": [],
            }
        return {
            "success": True,
            "message": "[Skipped] No changes detected.",
            "commit": "",
            "files": [],
        }

    system_files = classified["system"]

    # Stage only system files
    for f in system_files:
        ok, out = _run_git(["add", "--", f], cwd=root)
        if not ok:
            return {
                "success": False,
                "message": f"git add failed for '{f}': {out}",
                "commit": "",
                "files": [],
            }

    # Commit message
    if message is None:
        message = _generate_commit_message(system_files)

    ok, out = _run_git(["commit", "-m", message], cwd=root)
    if not ok:
        if "nothing to commit" in out.lower() or "no changes" in out.lower():
            return {
                "success": True,
                "message": "[Skipped] Nothing new to commit.",
                "commit": "",
                "files": [],
            }
        return {
            "success": False,
            "message": f"git commit failed: {out}",
            "commit": "",
            "files": [],
        }

    commit_hash = _get_short_hash(root)

    # Push
    branch = _get_current_branch(root)
    ok, out = _run_git(["push", "origin", branch], cwd=root)
    if not ok:
        return {
            "success": False,
            "message": f"Commit {commit_hash} created but push FAILED: {out}",
            "commit": commit_hash,
            "files": system_files,
        }

    return {
        "success": True,
        "message": f"Push SUCCESS to origin/{branch}",
        "commit": commit_hash,
        "files": system_files,
    }


def auto_sync() -> dict:
    """
    Full auto-sync workflow:
    1. Detect changes
    2. Classify
    3. Commit + push (if system changes exist)

    Returns same dict as sync_push, plus "mode" and "report".
    """
    files = detect_changed_files()

    if not files:
        return {
            "success": True,
            "mode": "skipped",
            "message": "[Skipped] No changes detected.",
            "commit": "",
            "files": [],
            "report": _build_report("skipped", [], "", ""),
        }

    classified = classify_changes(files)

    if not classified["system"]:
        return {
            "success": True,
            "mode": "skipped",
            "message": "[Skipped] Only problem outputs changed. GitHub sync ignored.",
            "commit": "",
            "files": [],
            "report": _build_report("skipped", classified["output"], "", ""),
        }

    result = sync_push(files=files)
    result["mode"] = "executed" if result["success"] else "failed"
    result["report"] = _build_report(
        result["mode"],
        result.get("files", []),
        result.get("commit", ""),
        result.get("message", ""),
    )
    return result


# ──────────────────────────────────────────────────────────────
# Report formatting
# ──────────────────────────────────────────────────────────────
def _build_report(
    mode: str,
    changed_files: list[str],
    commit_hash: str,
    push_message: str,
) -> str:
    """Build the formatted GitHub Auto Sync Report."""
    remote = _get_remote_url()
    branch = _get_current_branch()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "",
        "=" * 50,
        "  GitHub Auto Sync Report",
        "=" * 50,
        "",
        f"  Time: {timestamp}",
        f"  Branch: {branch}",
        "",
    ]

    if mode == "skipped":
        lines.append("  Mode: [Skipped] No system updates")
        if changed_files:
            lines.append("")
            lines.append("  Output files ignored:")
            for f in sorted(changed_files)[:10]:
                lines.append(f"    - {f}")
            if len(changed_files) > 10:
                lines.append(f"    ... +{len(changed_files) - 10} more")
    elif mode == "executed":
        lines.append("  Mode: [Executed] Auto-synced to GitHub")
        lines.append("")
        lines.append("  Files Changed:")
        for f in sorted(changed_files):
            lines.append(f"    - {f}")
        lines.append("")
        lines.append(f"  Commit: {commit_hash}")
        lines.append(f"  GitHub: {remote}")
        lines.append("")
        lines.append("  Push: SUCCESS")
    else:
        lines.append("  Mode: [Failed] Sync encountered an error")
        lines.append(f"  Error: {push_message}")

    lines.append("")
    lines.append("=" * 50)
    lines.append("")

    return "\n".join(lines)


def print_sync_report(result: dict | None = None):
    """Print the sync report. If no result, run auto_sync first."""
    if result is None:
        result = auto_sync()
    print(result.get("report", ""))


# ──────────────────────────────────────────────────────────────
# Status report (for `python main.py status`)
# ──────────────────────────────────────────────────────────────
def get_status_report() -> str:
    """Generate a full git status report."""
    root = get_project_root()
    remote = _get_remote_url(root)
    branch = _get_current_branch(root)
    commit = _get_short_hash(root)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "",
        "=" * 50,
        "  GitHub Sync Status",
        "=" * 50,
        "",
        f"  Time:     {timestamp}",
        f"  Branch:   {branch}",
        f"  Commit:   {commit}",
        f"  Remote:   {remote}",
        "",
    ]

    # Unpushed commits
    ok, out = _run_git(["log", "--oneline", "origin..HEAD", "--"], cwd=root)
    if ok and out:
        unpushed = out.splitlines()
        lines.append(f"  Unpushed commits: {len(unpushed)}")
        for c in unpushed[:5]:
            lines.append(f"    {c}")
    else:
        lines.append("  Unpushed commits: 0 (in sync)")

    lines.append("")

    # Recent 5 commits
    ok, out = _run_git(["log", "--oneline", "-5", "--decorate", "--"], cwd=root)
    if ok and out:
        lines.append("  Recent commits:")
        for c in out.splitlines():
            lines.append(f"    {c}")
    lines.append("")

    # Current changes
    files = detect_changed_files()
    if files:
        classified = classify_changes(files)
        lines.append(f"  Pending changes: {len(files)} file(s)")
        if classified["system"]:
            lines.append(f"    System: {len(classified['system'])}")
            for f in sorted(classified["system"])[:5]:
                lines.append(f"      - {f}")
            if len(classified["system"]) > 5:
                lines.append(f"      ... +{len(classified['system']) - 5} more")
        if classified["output"]:
            lines.append(f"    Output (ignored): {len(classified['output'])}")
    else:
        lines.append("  Working tree: clean")

    lines.append("")
    lines.append("=" * 50)
    lines.append("")

    return "\n".join(lines)
