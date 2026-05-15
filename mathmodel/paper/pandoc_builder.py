"""
Pandoc Builder

Converts Markdown to docx using Pandoc with OMML math support.

Usage:
    from mathmodel.paper.pandoc_builder import build_docx
    build_docx("final_paper.md", "final_paper.docx", template="template.docx")
"""

import subprocess
import shutil
from pathlib import Path


def find_pandoc() -> str:
    """Find pandoc binary path."""
    # Try system PATH
    pandoc = shutil.which("pandoc")
    if pandoc:
        return pandoc

    # Try common Windows locations
    candidates = [
        Path.home() / "AppData/Local/Pandoc/pandoc.exe",
        Path.home() / "AppData/Local/Microsoft/WinGet/Packages/JohnMacFarlane.Pandoc_Microsoft.Winget.Source_8wekyb3d8bbwe",
    ]
    for base in candidates:
        if base.is_dir():
            for p in base.rglob("pandoc.exe"):
                return str(p)
        elif base.exists():
            return str(base)

    # Search WinGet packages
    winget_dir = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    if winget_dir.exists():
        for p in winget_dir.rglob("pandoc.exe"):
            return str(p)

    raise FileNotFoundError("Pandoc not found. Install with: winget install JohnMacFarlane.Pandoc")


def build_docx(
    md_path: str | Path,
    docx_path: str | Path,
    template: str | Path | None = None,
    resource_path: str | Path | None = None,
    extra_args: list[str] | None = None,
) -> dict:
    """
    Convert Markdown to docx using Pandoc.

    Args:
        md_path: Input Markdown file
        docx_path: Output docx file
        template: Reference docx template for styling
        resource_path: Directory for resolving image paths
        extra_args: Additional Pandoc arguments

    Returns:
        {"success": bool, "message": str, "log": str}
    """
    pandoc = find_pandoc()
    md_path = Path(md_path)
    docx_path = Path(docx_path)

    if not md_path.exists():
        return {"success": False, "message": f"Input not found: {md_path}", "log": ""}

    docx_path.parent.mkdir(parents=True, exist_ok=True)

    # Build command
    cmd = [
        pandoc,
        str(md_path),
        "-o", str(docx_path),
        "--mathml",           # Convert LaTeX to OMML (Office Math)
        "--wrap=none",        # Don't wrap lines
        "--toc",              # Table of contents
        "--toc-depth=3",      # TOC depth
    ]

    if template and Path(template).exists():
        cmd.extend(["--reference-doc", str(template)])

    if resource_path:
        cmd.extend(["--resource-path", str(resource_path)])

    if extra_args:
        cmd.extend(extra_args)

    # Run Pandoc
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        log = f"Command: {' '.join(cmd)}\n"
        log += f"Return code: {result.returncode}\n"
        if result.stdout:
            log += f"Stdout: {result.stdout}\n"
        if result.stderr:
            log += f"Stderr: {result.stderr}\n"

        if result.returncode == 0 and docx_path.exists():
            return {
                "success": True,
                "message": f"Generated: {docx_path}",
                "log": log,
            }
        else:
            return {
                "success": False,
                "message": f"Pandoc failed (code {result.returncode})",
                "log": log,
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Pandoc timed out", "log": ""}
    except Exception as e:
        return {"success": False, "message": str(e), "log": ""}


def build_from_ir(ir_path: str | Path, docx_path: str | Path, template: str | Path | None = None) -> dict:
    """
    Full pipeline: IR → Markdown → docx.

    Args:
        ir_path: Path to paper_ir.json
        docx_path: Output docx path
        template: Optional reference docx template

    Returns:
        {"success": bool, "message": str, "log": str, "md_path": str}
    """
    from .ir import PaperIR
    from .renderer import render_to_file

    ir_path = Path(ir_path)
    docx_path = Path(docx_path)

    # Load IR
    ir = PaperIR.load(ir_path)

    # Render to Markdown
    md_path = docx_path.parent / "final_paper.md"
    render_to_file(ir, md_path)

    # Find resource path (for images)
    resource_path = None
    if ir.figures_dir:
        resource_path = ir.figures_dir

    # Build docx
    result = build_docx(md_path, docx_path, template=template, resource_path=resource_path)
    result["md_path"] = str(md_path)
    return result


def create_template(output_path: str | Path) -> Path:
    """
    Create a basic reference docx template with Chinese formatting.
    Requires pandoc to be installed.
    """
    pandoc = find_pandoc()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a minimal markdown for template generation
    minimal_md = output_path.parent / "_template_source.md"
    minimal_md.write_text("""---
title: "模板"
---

# 一级标题

正文内容。

## 二级标题

正文内容。

### 三级标题

正文内容。

$$
E = mc^2
$$

| 列1 | 列2 |
|-----|-----|
| A   | B   |

参考文献
""", encoding="utf-8")

    # Generate template docx
    cmd = [pandoc, str(minimal_md), "-o", str(output_path)]
    subprocess.run(cmd, capture_output=True, timeout=30)

    # Clean up
    minimal_md.unlink(missing_ok=True)

    return output_path
