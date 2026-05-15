"""
Paper Markdown Renderer

Converts Paper IR to Pandoc-compatible Markdown with LaTeX math.

Output: final_paper.md
"""

from pathlib import Path
from .ir import PaperIR, Section, ContentBlock


def render_markdown(ir: PaperIR) -> str:
    """
    Render Paper IR to Pandoc-compatible Markdown.

    Features:
    - $$...$$ for display math (Pandoc converts to OMML)
    - $...$ for inline math
    - ![](path) for figures with caption
    - Tables in pipe syntax
    - Auto-numbered equations
    """
    lines = []

    # ── Title ──
    if ir.title:
        lines.append(f"---")
        lines.append(f"title: \"{ir.title}\"")
        if ir.subtitle:
            lines.append(f"subtitle: \"{ir.subtitle}\"")
        lines.append(f"---")
        lines.append("")

    # ── Abstract ──
    if ir.abstract:
        lines.append("# 摘要")
        lines.append("")
        # Split into paragraphs
        for para in ir.abstract.split("\n\n"):
            para = para.strip()
            if para:
                lines.append(para)
                lines.append("")
        if ir.keywords:
            lines.append(f"**关键词：**{'；'.join(ir.keywords)}")
            lines.append("")

    # ── Sections ──
    eq_counter = [0]  # mutable counter

    for sec in ir.sections:
        # Section heading
        prefix = "#" * sec.level
        lines.append(f"{prefix} {sec.heading}")
        lines.append("")

        # Content blocks
        for block in sec.content:
            if isinstance(block, dict):
                block = ContentBlock(**{k: v for k, v in block.items()
                                        if k in ContentBlock.__dataclass_fields__})

            if block.type == "paragraph":
                lines.append(block.text)
                lines.append("")

            elif block.type == "equation":
                eq_counter[0] += 1
                num = eq_counter[0]
                label = block.label or str(num)
                lines.append(f"$$")
                lines.append(block.latex)
                lines.append(f"$$")
                lines.append(f"({num})")
                lines.append("")

            elif block.type == "figure":
                if block.path and Path(block.path).exists():
                    lines.append(f"![{block.caption}]({block.path}){{#fig:{block.ref}}}")
                    lines.append("")
                    if block.caption:
                        lines.append(f"*{block.ref}  {block.caption}*")
                        lines.append("")

            elif block.type == "table":
                if block.headers:
                    # Pipe table
                    lines.append("| " + " | ".join(str(h) for h in block.headers) + " |")
                    lines.append("| " + " | ".join("---" for _ in block.headers) + " |")
                    for row in block.rows:
                        lines.append("| " + " | ".join(str(c) for c in row) + " |")
                    lines.append("")
                    if block.caption:
                        lines.append(f"*{block.caption}*")
                        lines.append("")

            elif block.type == "list":
                for i, item in enumerate(block.items):
                    if block.ordered:
                        lines.append(f"{i+1}. {item}")
                    else:
                        lines.append(f"- {item}")
                lines.append("")

            elif block.type == "heading":
                lines.append(f"## {block.text}")
                lines.append("")

    # ── References ──
    if ir.references:
        lines.append("# 参考文献")
        lines.append("")
        for i, ref in enumerate(ir.references, 1):
            lines.append(f"[{i}] {ref}")
            lines.append("")

    return "\n".join(lines)


def render_to_file(ir: PaperIR, output_path: Path):
    """Render IR to Markdown file."""
    md = render_markdown(ir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")
    return output_path
