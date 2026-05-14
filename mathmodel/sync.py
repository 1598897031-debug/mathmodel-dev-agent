"""
GitHub Sync Module
Detects system-level changes and manages auto-commit/push.
Ensures only system code changes trigger git operations, not solve outputs.
"""

import subprocess
from pathlib import Path

# System-level paths that constitute "real" project changes
SYSTEM_PATHS = {
    "main.py",
    "requirements.txt",
    "README.md",
    "CLAUDE.md",
    "CASE_STUDY.md",
    ".gitignore",
    "pyproject.toml",
}

SYSTEM_DIRS = {
    "mathmodel/",
    "examples/",
    "tests/",
    "skills/",
    "problems/",
}


def _run_git(args: list[str], cwd: str | Path | None = None) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return result.returncode == 0, result.stdout.strip()
    except FileNotFoundError:
        return False, "git not installed"


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def detect_changed_files() -> list[str]:
    """Get list of all changed (staged + unstaged + untracked) files."""
    root = get_project_root()
    ok, output = _run_git(["status", "--porcelain"], cwd=root)
    if not ok:
        return []
    files = []
    for line in output.splitlines():
        # porcelain format: "XY filename" or "XY -> new_file" etc.
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            files.append(parts[1])
    return files


def classify_changes(files: list[str]) -> dict:
    """
    Classify changed files into 'system' and 'output' categories.

    Returns:
        {"system": [...], "output": [...]}
    """
    system_changes = []
    output_changes = []

    # Files/patterns to ignore entirely (stray files, secrets, etc.)
    IGNORE_PATTERNS = {
        "mimo token.txt", "「", ".env", ".env.local", ".env.*.local",
        "architect.png",
    }

    for f in files:
        path = Path(f)
        parts = path.parts

        # Skip stray/ignored files
        if f in IGNORE_PATTERNS:
            continue

        # Check if it's an output/temp/cache file
        if any(parts[0] == d for d in ("outputs", "temp", "cache", "tmp", "projects")):
            output_changes.append(f)
            continue
        if path.suffix in (".log",) and "execution.log" in f:
            output_changes.append(f)
            continue
        if f == "results.json":
            output_changes.append(f)
            continue

        # Check if it matches a system path
        if f in SYSTEM_PATHS:
            system_changes.append(f)
            continue
        if any(f.startswith(d) for d in SYSTEM_DIRS):
            system_changes.append(f)
            continue

        # Default: treat as system change (e.g., new config files)
        system_changes.append(f)

    return {"system": system_changes, "output": output_changes}


def has_system_changes(files: list[str] | None = None) -> bool:
    """Quick check: are there any system-level changes?"""
    if files is None:
        files = detect_changed_files()
    classified = classify_changes(files)
    return len(classified["system"]) > 0


def generate_summary(files: list[str] | None = None) -> str:
    """Generate a human-readable summary of changes."""
    if files is None:
        files = detect_changed_files()

    if not files:
        return "No changes detected."

    classified = classify_changes(files)
    lines = ["## Change Summary\n"]

    if classified["system"]:
        lines.append(f"### System changes ({len(classified['system'])})")
        for f in sorted(classified["system"]):
            lines.append(f"  - {f}")
        lines.append("")

    if classified["output"]:
        lines.append(f"### Output changes ({len(classified['output'])})")
        lines.append("  (will NOT be committed)")
        for f in sorted(classified["output"]):
            lines.append(f"  - {f}")
        lines.append("")

    if classified["system"]:
        lines.append("**Action**: System changes detected -- commit and push recommended.")
    else:
        lines.append("**Action**: Only output changes -- no commit needed.")

    return "\n".join(lines)


def sync_push(message: str | None = None) -> dict:
    """
    Stage system files, commit, and push.

    Returns:
        {"success": bool, "message": str, "summary": str}
    """
    root = get_project_root()
    files = detect_changed_files()
    classified = classify_changes(files)

    if not classified["system"]:
        return {
            "success": True,
            "message": "No system changes to commit.",
            "summary": "Only output files changed (or no changes at all). Nothing to push.",
        }

    # Add system files (use -- to handle special characters in filenames)
    for f in classified["system"]:
        ok, out = _run_git(["add", "--", f], cwd=root)
        if not ok:
            return {"success": False, "message": f"git add failed for '{f}': {out}", "summary": ""}

    # Generate commit message
    if message is None:
        changed_names = [Path(f).stem for f in classified["system"][:5]]
        message = f"system update: {', '.join(changed_names)}"
        if len(classified["system"]) > 5:
            message += f" +{len(classified['system']) - 5} more"

    # Commit
    ok, out = _run_git(["commit", "-m", message], cwd=root)
    if not ok:
        if "nothing to commit" in out.lower():
            return {"success": True, "message": "Nothing to commit.", "summary": ""}
        return {"success": False, "message": f"git commit failed: {out}", "summary": ""}

    # Push
    branch = _get_current_branch(root)
    ok, out = _run_git(["push", "origin", branch], cwd=root)
    if not ok:
        return {
            "success": False,
            "message": f"Commit succeeded but push failed: {out}",
            "summary": generate_summary(files),
        }

    return {
        "success": True,
        "message": f"Pushed to origin/{branch} successfully.",
        "summary": generate_summary(files),
    }


def _get_current_branch(cwd: Path) -> str:
    ok, output = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return output.strip() if ok else "master"
