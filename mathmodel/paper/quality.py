"""
Paper Quality Scoring System

Scores paper on 5 dimensions (20 points each) per national award standards.
Also provides figure consistency checking.

Usage:
    from mathmodel.paper.quality import score_paper, check_figure_consistency
    report = score_paper(Path("outputs/A_underwater_detection"))
"""

import json
import re
from pathlib import Path


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def score_paper(project_dir: Path) -> dict:
    """
    Score paper quality on 5 dimensions (20 points each).

    Returns:
        {
            "total": 0-100,
            "writing": 0-20,
            "figures": 0-20,
            "math": 0-20,
            "logic": 0-20,
            "engineering": 0-20,
            "details": [...],
        }
    """
    project_dir = Path(project_dir)
    ir_path = project_dir / "paper" / "paper_ir.json"
    md_path = project_dir / "paper" / "final_paper.md"

    ir = _load_json(ir_path)
    md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""

    details = []
    scores = {}

    # ── 1. Writing Quality (20pts) ──
    writing = 20
    # Check for AI traces
    ai_patterns = [
        "本文提出一种", "实验结果表明模型", "具有较强鲁棒性",
        "效果较好", "系统求解了", "具有良好", "综上所述",
    ]
    for pat in ai_patterns:
        if pat in md:
            writing -= 3
            details.append(f"AI痕迹: '{pat}'")

    # Check for data-backed conclusions
    data_refs = len(re.findall(r'表\d|图\d|\d+\.\d+(?:ms|m|%)', md))
    if data_refs < 10:
        writing -= 5
        details.append(f"数据引用不足: {data_refs}处")
    elif data_refs < 20:
        writing -= 2

    scores["writing"] = max(0, writing)

    # ── 2. Figure Quality (20pts) ──
    figures = 20
    fig_dir = project_dir / "figures"
    ir_figs = []
    for sec in ir.get("sections", []):
        for block in sec.get("content", []):
            if block.get("type") == "figure":
                ir_figs.append(block)

    # Check figure existence
    missing_figs = 0
    for fig in ir_figs:
        p = Path(fig.get("path", ""))
        if not p.exists():
            missing_figs += 1
            details.append(f"图缺失: {fig.get('ref', '?')}")

    if missing_figs > 0:
        figures -= missing_figs * 5

    # Check figure references in text
    unreferenced = 0
    for fig in ir_figs:
        ref = fig.get("ref", "")
        if ref and ref not in md:
            unreferenced += 1
            details.append(f"图未引用: {ref}")
    if unreferenced > 0:
        figures -= unreferenced * 3

    # Check for Chinese captions
    non_chinese = 0
    for fig in ir_figs:
        cap = fig.get("caption", "")
        if cap and not re.search(r'[一-鿿]', cap):
            non_chinese += 1
    if non_chinese > 0:
        figures -= non_chinese * 2

    scores["figures"] = max(0, figures)

    # ── 3. Math Rigor (20pts) ──
    math = 20
    # Count equations
    eq_count = sum(1 for sec in ir.get("sections", [])
                   for block in sec.get("content", [])
                   if block.get("type") == "equation")
    if eq_count < 5:
        math -= 8
        details.append(f"公式不足: {eq_count}个")
    elif eq_count < 8:
        math -= 3

    # Check for code-style formulas
    code_patterns = ['np.', 'numpy.', 'math.', 'scipy.', 'import ', 'sqrt(', 'sum(']
    for pat in code_patterns:
        if pat in md:
            math -= 3
            details.append(f"代码公式: '{pat}'")

    scores["math"] = max(0, math)

    # ── 4. Logic Structure (20pts) ──
    logic = 20
    # Check section count
    sec_count = len(ir.get("sections", []))
    if sec_count < 8:
        logic -= 5
        details.append(f"章节不足: {sec_count}个")

    # Check for tables
    tbl_count = sum(1 for sec in ir.get("sections", [])
                    for block in sec.get("content", [])
                    if block.get("type") == "table")
    if tbl_count < 3:
        logic -= 5
        details.append(f"表格不足: {tbl_count}个")

    # Check for references
    ref_count = len(ir.get("references", []))
    if ref_count < 5:
        logic -= 3

    scores["logic"] = max(0, logic)

    # ── 5. Engineering Value (20pts) ──
    engineering = 20
    # Check for engineering keywords
    eng_keywords = ["实际", "工程", "应用", "探测", "路径规划", "自适应", "盲扫"]
    eng_found = sum(1 for kw in eng_keywords if kw in md)
    if eng_found < 3:
        engineering -= 8
        details.append(f"工程解释不足: {eng_found}个关键词")

    # Check for MC analysis
    if "Monte Carlo" not in md and "monte carlo" not in md.lower():
        engineering -= 5
        details.append("缺少Monte Carlo分析")

    # Check for sensitivity analysis
    if "灵敏度" not in md:
        engineering -= 3

    scores["engineering"] = max(0, engineering)

    total = sum(scores.values())

    return {
        "total": total,
        **scores,
        "details": details,
        "pass": total >= 90,
    }


def check_figure_consistency(project_dir: Path) -> dict:
    """
    Check figure-text consistency.

    Returns:
        {
            "consistent": bool,
            "total_figs": int,
            "referenced": int,
            "unreferenced": list[str],
            "missing": list[str],
        }
    """
    project_dir = Path(project_dir)
    ir_path = project_dir / "paper" / "paper_ir.json"
    md_path = project_dir / "paper" / "final_paper.md"

    ir = _load_json(ir_path)
    md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""

    all_figs = []
    for sec in ir.get("sections", []):
        for block in sec.get("content", []):
            if block.get("type") == "figure":
                all_figs.append(block)

    unreferenced = []
    missing = []

    for fig in all_figs:
        ref = fig.get("ref", "")
        path = fig.get("path", "")

        if ref and ref not in md:
            unreferenced.append(ref)

        if path and not Path(path).exists():
            missing.append(ref or path)

    return {
        "consistent": len(unreferenced) == 0 and len(missing) == 0,
        "total_figs": len(all_figs),
        "referenced": len(all_figs) - len(unreferenced),
        "unreferenced": unreferenced,
        "missing": missing,
    }


def print_quality_report(project_dir: Path):
    """Print a formatted quality report."""
    report = score_paper(project_dir)
    consistency = check_figure_consistency(project_dir)

    print("=" * 55)
    print("  Paper Quality Report (国奖标准)")
    print("=" * 55)
    print()
    print(f"  总分: {report['total']}/100  {'PASS' if report['pass'] else 'FAIL'}")
    print()
    print(f"  写作规范:     {report['writing']}/20")
    print(f"  图表质量:     {report['figures']}/20")
    print(f"  数学严谨性:   {report['math']}/20")
    print(f"  逻辑结构:     {report['logic']}/20")
    print(f"  工程解释性:   {report['engineering']}/20")
    print()
    print(f"  图文一致性:   {'PASS' if consistency['consistent'] else 'FAIL'}")
    print(f"  图总数:       {consistency['total_figs']}")
    print(f"  已引用:       {consistency['referenced']}")
    if consistency['unreferenced']:
        print(f"  未引用:       {consistency['unreferenced']}")
    if consistency['missing']:
        print(f"  缺失:         {consistency['missing']}")
    print()

    if report['details']:
        print("  问题清单:")
        for d in report['details']:
            print(f"    - {d}")
    else:
        print("  无问题")

    print("=" * 55)
    return report
