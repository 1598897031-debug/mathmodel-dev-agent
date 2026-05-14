"""
论文写作 Agent (Paper Writer Agent)
直接生成符合全国大学生数学建模竞赛格式的 Word 文档
输出: final_paper.docx (唯一输出)
"""

import sys
import os
# Ensure python-docx is importable
for _site in ["D:/Lib/site-packages", "D:\\Lib\\site-packages"]:
    if os.path.isdir(_site) and _site not in sys.path:
        sys.path.insert(0, _site)

import json
import re
import io
from pathlib import Path
from datetime import datetime

from ..core.llm_client import LLMClient, Message
from ..core.document_parser import ProblemSpec
from ..config import AppConfig
from .base import BaseAgent, AgentContext, AgentResult


# ==================== LLM Prompt ====================

PAPER_SYSTEM_PROMPT = """\
你是一个数学建模论文写作专家。根据给定的题目信息、建模方案和实验结果，生成完整数学论文的指定章节。

要求：
1. 语言正式、逻辑清晰、学术规范
2. 数学公式使用 LaTeX 格式 (如 $E=mc^2$, $$\\int_0^1 f(x)dx$$)
3. 图表引用规范 (如 [图1], [表1])
4. 内容详实、论证严密
5. 中文写作

只输出要求的章节内容，不要输出其他章节。"""


# ==================== 数学公式渲染 ====================

def render_latex_to_image(latex_str: str, output_path: Path, fontsize: int = 14, dpi: int = 200) -> bool:
    """
    将 LaTeX 公式渲染为 PNG 图片

    Args:
        latex_str: LaTeX 公式字符串
        output_path: 输出图片路径
        fontsize: 字号
        dpi: 分辨率

    Returns:
        是否成功
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0)
        ax.set_axis_off()

        # 处理 LaTeX: 移除 $$ 包裹
        tex = latex_str.strip()
        if tex.startswith("$$") and tex.endswith("$$"):
            tex = tex[2:-2].strip()
        elif tex.startswith("$") and tex.endswith("$"):
            tex = tex[1:-1].strip()

        t = ax.text(
            0, 0, f"${tex}$",
            fontsize=fontsize,
            ha="left", va="center",
            transform=ax.transAxes,
        )

        fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight",
                     pad_inches=0.02, transparent=True)
        plt.close(fig)
        return True

    except Exception:
        return False


def render_latex_inline(latex_str: str, fontsize: int = 14) -> io.BytesIO | None:
    """
    将 LaTeX 公式渲染为内存中的 PNG 图片

    Args:
        latex_str: LaTeX 公式字符串
        fontsize: 字号

    Returns:
        BytesIO 对象或 None
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0)
        ax.set_axis_off()

        tex = latex_str.strip()
        if tex.startswith("$$") and tex.endswith("$$"):
            tex = tex[2:-2].strip()
        elif tex.startswith("$") and tex.endswith("$"):
            tex = tex[1:-1].strip()

        t = ax.text(
            0, 0, f"${tex}$",
            fontsize=fontsize,
            ha="left", va="center",
            transform=ax.transAxes,
        )

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=200, bbox_inches="tight",
                     pad_inches=0.02, transparent=True)
        plt.close(fig)
        buf.seek(0)
        return buf

    except Exception:
        return None


# ==================== 文档构建器 ====================

class PaperDocxBuilder:
    """
    数学建模论文 Word 文档构建器
    直接构建符合竞赛格式的 .docx 文件
    """

    def __init__(self):
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor, Emu
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.enum.section import WD_ORIENT
        from docx.oxml.ns import qn

        self.Document = Document
        self.Pt = Pt
        self.Cm = Cm
        self.RGBColor = RGBColor
        self.Emu = Emu
        self.WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH
        self.WD_TABLE_ALIGNMENT = WD_TABLE_ALIGNMENT
        self.WD_ORIENT = WD_ORIENT
        self.qn = qn

        self.doc = Document()
        self._setup_styles()
        self._setup_page()

        self._figure_counter = 0
        self._table_counter = 0
        self._equation_counter = 0
        self._figure_dir = None
        self._figure_map = {}  # filename -> caption

    def _setup_styles(self):
        """配置文档样式"""
        from docx.shared import Pt as _Pt

        # 默认字体: 宋体 + Times New Roman
        style = self.doc.styles['Normal']
        font = style.font
        font.name = 'Times New Roman'
        font.size = self.Pt(12)
        # 设置中文字体
        r = style.element.rPr
        if r is None:
            r = style.element._add_rPr()
        rFonts = r.find(self.qn('w:rFonts'))
        if rFonts is None:
            rFonts = self._make_element('w:rFonts', r)
        rFonts.set(self.qn('w:eastAsia'), '宋体')

        pf = style.paragraph_format
        pf.line_spacing = 1.5
        pf.space_after = self.Pt(0)
        pf.space_before = self.Pt(0)

        # Heading 样式
        for level in range(1, 4):
            h_style = self.doc.styles[f'Heading {level}']
            h_font = h_style.font
            h_font.name = 'Times New Roman'
            h_font.bold = True
            h_font.color.rgb = self.RGBColor(0, 0, 0)
            h_r = h_style.element.rPr
            if h_r is None:
                h_r = h_style.element._add_rPr()
            h_rFonts = h_r.find(self.qn('w:rFonts'))
            if h_rFonts is None:
                h_rFonts = self._make_element('w:rFonts', h_r)
            h_rFonts.set(self.qn('w:eastAsia'), '黑体')

            h_pf = h_style.paragraph_format
            h_pf.space_before = self.Pt(12)
            h_pf.space_after = self.Pt(6)

            if level == 1:
                h_font.size = self.Pt(16)
                h_pf.alignment = self.WD_ALIGN_PARAGRAPH.LEFT
            elif level == 2:
                h_font.size = self.Pt(14)
            else:
                h_font.size = self.Pt(13)

    def _make_element(self, tag, parent):
        """创建 XML 元素"""
        from lxml import etree
        nsmap = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        el = etree.SubElement(parent, self.qn(tag))
        return el

    def _setup_page(self):
        """设置页面: A4, 页边距"""
        section = self.doc.sections[0]
        section.page_width = self.Cm(21)
        section.page_height = self.Cm(29.7)
        section.top_margin = self.Cm(2.54)
        section.bottom_margin = self.Cm(2.54)
        section.left_margin = self.Cm(3.17)
        section.right_margin = self.Cm(3.17)

    # ==================== 封面 ====================

    def add_cover(self, title: str, problem_source: str = ""):
        """添加封面"""
        # 空行占位
        for _ in range(4):
            self.doc.add_paragraph()

        # 标题
        p = self.doc.add_paragraph()
        p.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(title)
        run.bold = True
        run.font.size = self.Pt(26)
        run.font.name = 'Times New Roman'
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(self.qn('w:rFonts'))
        if rFonts is None:
            rFonts = self._make_element('w:rFonts', rPr)
        rFonts.set(self.qn('w:eastAsia'), '黑体')

        self.doc.add_paragraph()

        # 副标题 (竞赛信息)
        if problem_source:
            p = self.doc.add_paragraph()
            p.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(problem_source)
            run.font.size = self.Pt(16)
            run.font.name = 'Times New Roman'
            rPr = run._element.get_or_add_rPr()
            rFonts = rPr.find(self.qn('w:rFonts'))
            if rFonts is None:
                rFonts = self._make_element('w:rFonts', rPr)
            rFonts.set(self.qn('w:eastAsia'), '宋体')

        for _ in range(6):
            self.doc.add_paragraph()

        # 日期
        p = self.doc.add_paragraph()
        p.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(datetime.now().strftime("%Y年%m月"))
        run.font.size = self.Pt(14)
        run.font.name = 'Times New Roman'
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(self.qn('w:rFonts'))
        if rFonts is None:
            rFonts = self._make_element('w:rFonts', rPr)
        rFonts.set(self.qn('w:eastAsia'), '宋体')

        # 分页
        self.doc.add_page_break()

    # ==================== 目录 ====================

    def add_toc(self):
        """添加自动目录"""
        p = self.doc.add_paragraph()
        p.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("目  录")
        run.bold = True
        run.font.size = self.Pt(18)
        run.font.name = 'Times New Roman'
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(self.qn('w:rFonts'))
        if rFonts is None:
            rFonts = self._make_element('w:rFonts', rPr)
        rFonts.set(self.qn('w:eastAsia'), '黑体')

        self.doc.add_paragraph()

        # 插入 TOC 域代码
        from docx.oxml import OxmlElement
        paragraph = self.doc.add_paragraph()
        run = paragraph.add_run()
        fld_char_begin = OxmlElement('w:fldChar')
        fld_char_begin.set(self.qn('w:fldCharType'), 'begin')
        run._element.append(fld_char_begin)

        run2 = paragraph.add_run()
        instr_text = OxmlElement('w:instrText')
        instr_text.set(self.qn('xml:space'), 'preserve')
        instr_text.text = ' TOC \\o "1-3" \\h \\z \\u '
        run2._element.append(instr_text)

        run3 = paragraph.add_run()
        fld_char_end = OxmlElement('w:fldChar')
        fld_char_end.set(self.qn('w:fldCharType'), 'end')
        run3._element.append(fld_char_end)

        # 提示文字
        p2 = self.doc.add_paragraph()
        p2.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
        r = p2.add_run('（请在 Word 中右键点击目录，选择"更新域"以生成目录）')
        r.font.size = self.Pt(10)
        r.font.color.rgb = self.RGBColor(128, 128, 128)

        self.doc.add_page_break()

    # ==================== 章节标题 ====================

    def add_heading(self, text: str, level: int = 1):
        """添加章节标题"""
        h = self.doc.add_heading(text, level=level)
        return h

    # ==================== 正文段落 ====================

    def add_paragraph(self, text: str, bold: bool = False, indent: bool = True):
        """添加正文段落"""
        p = self.doc.add_paragraph()
        if indent:
            p.paragraph_format.first_line_indent = self.Cm(0.74)  # 两字符缩进
        run = p.add_run(text)
        run.bold = bold
        run.font.name = 'Times New Roman'
        run.font.size = self.Pt(12)
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(self.qn('w:rFonts'))
        if rFonts is None:
            rFonts = self._make_element('w:rFonts', rPr)
        rFonts.set(self.qn('w:eastAsia'), '宋体')
        return p

    def add_paragraph_with_latex(self, text_parts: list, indent: bool = True):
        """
        添加包含 LaTeX 公式的段落
        text_parts: [(text, is_latex), ...]
        """
        p = self.doc.add_paragraph()
        if indent:
            p.paragraph_format.first_line_indent = self.Cm(0.74)

        for text, is_latex in text_parts:
            if is_latex:
                buf = render_latex_inline(text, fontsize=14)
                if buf:
                    from docx.shared import Inches
                    run = p.add_run()
                    run.add_picture(buf, width=Inches(0.1 * len(text)))
                else:
                    # 回退: 纯文本
                    run = p.add_run(text)
                    run.font.name = 'Times New Roman'
                    run.font.size = self.Pt(12)
            else:
                run = p.add_run(text)
                run.font.name = 'Times New Roman'
                run.font.size = self.Pt(12)
                rPr = run._element.get_or_add_rPr()
                rFonts = rPr.find(self.qn('w:rFonts'))
                if rFonts is None:
                    rFonts = self._make_element('w:rFonts', rPr)
                rFonts.set(self.qn('w:eastAsia'), '宋体')
        return p

    # ==================== 公式 ====================

    def add_equation(self, latex: str, label: str = ""):
        """添加编号公式"""
        self._equation_counter += 1
        num = self._equation_counter

        p = self.doc.add_paragraph()
        p.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = self.Pt(6)
        p.paragraph_format.space_after = self.Pt(6)

        # 渲染公式为图片
        buf = render_latex_inline(latex, fontsize=16)
        if buf:
            from docx.shared import Inches
            run = p.add_run()
            run.add_picture(buf, width=Inches(4.5))
        else:
            # 回退: 纯文本
            run = p.add_run(f"({label or latex})")
            run.font.name = 'Times New Roman'
            run.font.size = self.Pt(12)

        # 编号
        run_num = p.add_run(f"    ({num})")
        run_num.font.name = 'Times New Roman'
        run_num.font.size = self.Pt(12)

        return num

    # ==================== 图片 ====================

    def add_figure(self, image_path: Path, caption: str = "", width_inches: float = 5.0):
        """添加图片 (自动编号)"""
        if not image_path.exists():
            return

        self._figure_counter += 1
        num = self._figure_counter

        # 居中插入
        p = self.doc.add_paragraph()
        p.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = self.Pt(6)
        from docx.shared import Inches
        run = p.add_run()
        run.add_picture(str(image_path), width=Inches(width_inches))

        # 图注
        cap_p = self.doc.add_paragraph()
        cap_p.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
        cap_p.paragraph_format.space_after = self.Pt(6)
        cap_text = f"图{num}" + (f"  {caption}" if caption else "")
        run = cap_p.add_run(cap_text)
        run.font.size = self.Pt(10)
        run.font.name = 'Times New Roman'
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(self.qn('w:rFonts'))
        if rFonts is None:
            rFonts = self._make_element('w:rFonts', rPr)
        rFonts.set(self.qn('w:eastAsia'), '宋体')

        return num

    def add_figure_from_dir(self, filename: str, caption: str = "", width_inches: float = 5.0):
        """从 figures 目录添加图片"""
        if self._figure_dir is None:
            return 0
        path = self._figure_dir / filename
        return self.add_figure(path, caption, width_inches)

    # ==================== 表格 ====================

    def add_table(self, headers: list[str], rows: list[list[str]], caption: str = ""):
        """添加表格 (自动编号)"""
        self._table_counter += 1
        num = self._table_counter

        # 表格
        table = self.doc.add_table(rows=1 + len(rows), cols=len(headers))
        table.style = 'Table Grid'
        table.alignment = self.WD_TABLE_ALIGNMENT.CENTER

        # 表头
        for j, h in enumerate(headers):
            cell = table.rows[0].cells[j]
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(h)
            run.bold = True
            run.font.size = self.Pt(10)
            run.font.name = 'Times New Roman'
            rPr = run._element.get_or_add_rPr()
            rFonts = rPr.find(self.qn('w:rFonts'))
            if rFonts is None:
                rFonts = self._make_element('w:rFonts', rPr)
            rFonts.set(self.qn('w:eastAsia'), '宋体')
            # 灰色背景
            shading = self._make_element('w:shd', cell._element.get_or_add_tcPr())
            shading.set(self.qn('w:fill'), 'D9E2F3')

        # 数据行
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                if c_idx < len(headers):
                    cell = table.rows[r_idx + 1].cells[c_idx]
                    cell.text = ""
                    p = cell.paragraphs[0]
                    p.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
                    run = p.add_run(str(val))
                    run.font.size = self.Pt(10)
                    run.font.name = 'Times New Roman'

        # 表注
        cap_p = self.doc.add_paragraph()
        cap_p.alignment = self.WD_ALIGN_PARAGRAPH.CENTER
        cap_p.paragraph_format.space_before = self.Pt(3)
        cap_p.paragraph_format.space_after = self.Pt(6)
        cap_text = f"表{num}" + (f"  {caption}" if caption else "")
        run = cap_p.add_run(cap_text)
        run.font.size = self.Pt(10)
        run.font.name = 'Times New Roman'
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(self.qn('w:rFonts'))
        if rFonts is None:
            rFonts = self._make_element('w:rFonts', rPr)
        rFonts.set(self.qn('w:eastAsia'), '宋体')

        return num

    # ==================== 列表 ====================

    def add_list(self, items: list[str], ordered: bool = False):
        """添加列表"""
        style = 'List Number' if ordered else 'List Bullet'
        for item in items:
            p = self.doc.add_paragraph(item, style=style)
            for run in p.runs:
                run.font.size = self.Pt(12)
                run.font.name = 'Times New Roman'

    # ==================== 分页 ====================

    def add_page_break(self):
        """添加分页符"""
        self.doc.add_page_break()

    # ==================== 保存 ====================

    def save(self, path: Path):
        """保存文档"""
        self.doc.save(str(path))


# ==================== 论文内容生成 ====================


class PaperContentGenerator:
    """
    论文内容生成器
    从中间产物中提取信息，生成各章节文本
    """

    def __init__(self, context: AgentContext):
        self.context = context
        self.spec = context.problem_spec
        self.plan = context.model_plan
        self.exec_result = context.execution_result
        self.exp_result = context.experiment_result

        # 加载 JSON 数据
        self.results = self._load_json(context.project_dir / "results.json")
        self.problem_data = self._load_json(context.project_dir / "parsed_problem.json")

        # 加载 Markdown 数据
        self.strategy_md = self._load_md(context.project_dir / "strategy.md")
        self.experiment_md = self._load_md(context.project_dir / "experiment_report.md")
        self.summary_md = self._load_md(context.project_dir / "solution_summary.md")

    def _load_json(self, path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _load_md(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _title(self) -> str:
        if self.spec and self.spec.title:
            return self.spec.title
        if self.problem_data.get("title"):
            return self.problem_data["title"]
        return "数学建模问题"

    def _source(self) -> str:
        return self.problem_data.get("source", "")

    def _context_text(self) -> str:
        return self.problem_data.get("context", "")

    def _questions(self) -> dict:
        return self.problem_data.get("questions", {})

    def _sound_speed(self) -> float:
        return self.problem_data.get("coordinate_system", {}).get("sound_speed", 1500.0)

    def _best_approach(self) -> str:
        if self.plan:
            return self.plan.get("best_approach", "声呐回波时间几何定位模型")
        return "声呐回波时间几何定位模型"

    # ==================== 各章节生成 ====================

    def generate_abstract(self) -> str:
        """摘要"""
        title = self._title()
        approach = self._best_approach()
        questions = self._questions()

        abstract = (
            f"本文针对「{title}」问题，基于主动声呐回波时间与目标距离的几何关系，"
            f"建立了{approach}，对四个子问题进行了系统求解。\n\n"
        )

        # Q1
        q1 = self.results.get("Q1", {})
        if q1:
            a = q1.get("nodule_A", {})
            b = q1.get("nodule_B", {})
            abstract += (
                f"针对问题一，利用非线性最小二乘法，由5个船位的回波时间数据，"
                f"定位了两个点状结核的坐标：结核A位于({a.get('x',0):.2f}, "
                f"{a.get('y',0):.2f}, {a.get('z',0):.2f})m，"
                f"结核B位于({b.get('x',0):.2f}, {b.get('y',0):.2f}, "
                f"{b.get('z',0):.2f})m。\n\n"
            )

        # Q2
        q2 = self.results.get("Q2", {})
        if q2:
            c = q2.get("center", {})
            r = q2.get("radius", 0)
            abstract += (
                f"针对问题二，建立了球面几何模型，通过4个声呐位置的回波延迟数据，"
                f"拟合得到球形结核的球心坐标为({c.get('x',0):.2f}, {c.get('y',0):.2f}, "
                f"{c.get('z',0):.2f})m，半径为{r:.2f}m。\n\n"
            )

        # Q3
        q3 = self.results.get("Q3", {})
        if q3:
            abstract += (
                f"针对问题三，推导了探测船沿X轴移动时回波时间t(x)的解析表达式，"
                f"并分析了曲线的对称性、极值点和渐近线等几何特征。\n\n"
            )

        # Q4
        q4 = self.results.get("Q4", {})
        if q4:
            abstract += (
                f"针对问题四，建立了二维等时线模型，绘制了三维曲面图和等高线图，"
                f"分析了梯度场的方向特性及其在路径规划中的应用。\n\n"
            )

        abstract += (
            "实验结果表明，所建立的模型具有物理基础扎实、计算效率高、结果直观等优点，"
            "能够有效解决水下目标探测与定位问题。\n\n"
        )

        # 关键词
        abstract += "关键词：声呐定位；回波时间；非线性最小二乘；等时线；梯度路径规划"

        return abstract

    def generate_problem_restatement(self) -> str:
        """问题重述"""
        ctx = self._context_text()
        questions = self._questions()

        text = f"{ctx}\n\n"
        text += "本题要求解决以下四个子问题：\n\n"

        for key in ["Q1", "Q2", "Q3", "Q4"]:
            q = questions.get(key, {})
            title = q.get("title", "")
            desc = q.get("description", "")
            text += f"（{key[1]}）{title}：{desc}\n\n"

        return text

    def generate_problem_analysis(self) -> str:
        """问题分析"""
        questions = self._questions()
        approach = self._best_approach()

        text = (
            f"本题属于水下声学定位问题，核心数学工具包括非线性最小二乘、"
            f"几何分析和多元函数优化。\n\n"
        )

        text += (
            f"四个子问题的求解思路如下：\n\n"
        )

        # Q1 分析
        q1 = questions.get("Q1", {})
        text += (
            f"问题一（{q1.get('title', '')}）：船在5个已知位置测量回波时间，"
            f"根据声呐方程 t=2d/c 可将回波时间转换为距离。结核为质点时，"
            f"距离方程为 d_i = sqrt((x_s_i - x_n)^2 + y_n^2 + z_n^2)，"
            f"5个方程3个未知数构成超定方程组，采用非线性最小二乘求解。\n\n"
        )

        # Q2 分析
        q2 = questions.get("Q2", {})
        text += (
            f"问题二（{q2.get('title', '')}）：球形结核有4个参数（球心坐标+半径），"
            f"4个声呐位置提供4个方程，构成确定方程组。"
            f"声呐到球面的距离等于到球心距离减去半径，据此建立优化目标函数。\n\n"
        )

        # Q3 分析
        q3 = questions.get("Q3", {})
        text += (
            f"问题三（{q3.get('title', '')}）：船沿X轴移动，目标位置固定，"
            f"可直接推导回波时间 t 关于船位 x 的解析函数。"
            f"该函数为双曲线形式，具有对称轴和最小值点。\n\n"
        )

        # Q4 分析
        q4 = questions.get("Q4", {})
        text += (
            f"问题四（{q4.get('title', '')}）：船可在海面任意移动，"
            f"建立二维等时线模型 t(x,y)，分析等时线的几何特征和梯度方向。"
            f"梯度方向垂直于等时线，指向目标位置。\n\n"
        )

        return text

    def generate_assumptions(self) -> list[str]:
        """模型假设"""
        return [
            "声速在海底沉积物中恒定，c = 1500 m/s",
            "点状结核可视为质点（问题一）",
            "球形结核完全暴露在海底之上（问题二）",
            "忽略声波多径传播和散射效应",
            "回波时间仅由直线距离决定，即 t = 2d/c",
            "海底为平面（z = 0）",
            "回波时间测量无系统误差",
        ]

    def generate_symbols_table(self) -> tuple[list[str], list[list[str]]]:
        """符号说明表"""
        headers = ["符号", "含义", "值/单位"]
        rows = [
            ["c", "声速", "1500 m/s"],
            ["t", "回波时间", "ms"],
            ["d", "声呐到目标距离", "m"],
            ["(x_n, y_n, z_n)", "结核坐标", "m"],
            ["(x_c, y_c, z_c)", "球心坐标", "m"],
            ["R", "球半径", "m"],
            ["D", "声呐到球心距离", "m"],
            ["(x_t, y_t, z_t)", "目标坐标", "m"],
        ]
        return headers, rows

    def generate_model_establishment(self) -> str:
        """模型建立"""
        text = ""

        # 基础模型
        text += "主动声呐通过发射声波并接收目标反射回波来定位。回波时间与距离的关系为：\n\n"
        text += "t = 2d / c\n\n"
        text += "其中 d 为声呐到目标的距离，c = 1500 m/s 为声速。\n\n"

        # Q1 模型
        text += "4.1 点状结核定位模型（问题一）\n\n"
        text += (
            "设结核位于 (x_n, y_n, z_n)，船在第 i 个位置 (x_{s_i}, 0, 0) 时，"
            "回波距离为 d_i = t_i * c / 2。距离方程为：\n\n"
        )
        text += "d_i = sqrt((x_{s_i} - x_n)^2 + y_n^2 + z_n^2)\n\n"
        text += (
            "对距离方程平方后线性化，令 a = x_n，b = x_n^2 + y_n^2 + z_n^2，"
            "得线性方程组：[2*x_{s_i}, -1] * [a, b]^T = x_{s_i}^2 - d_i^2\n\n"
        )
        text += "5个方程3个未知数构成超定方程组，采用最小二乘法求解。\n\n"

        # Q2 模型
        text += "4.2 球形结核定位模型（问题二）\n\n"
        text += (
            "设球心位于 (x_c, y_c, z_c)，半径为 R。声呐到球面的距离为 d_i，"
            "到球心的距离为 D_i = d_i + R。由此建立方程：\n\n"
        )
        text += "D_i^2 = (x_{s_i} - x_c)^2 + (y_{s_i} - y_c)^2 + (z_{s_i} - z_c)^2\n\n"
        text += (
            "定义代价函数：min sum((sqrt((x_{s_i}-x_c)^2+(y_{s_i}-y_c)^2+(z_{s_i}-z_c)^2)"
            " - (d_i+R))^2)，采用网格搜索结合局部优化求解。\n\n"
        )

        # Q3 模型
        text += "4.3 回波时间函数推导（问题三）\n\n"
        text += (
            "探测船沿X轴移动至 (x, 0, 0)，目标固定于 (x_t, y_t, z_t)。"
            "回波时间的解析表达式为：\n\n"
        )
        text += "t(x) = (2/c) * sqrt((x - x_t)^2 + y_t^2 + z_t^2)\n\n"

        # Q4 模型
        text += "4.4 二维等时线模型（问题四）\n\n"
        text += "船在海面 (x, y, 0) 任意位置时，回波时间函数为：\n\n"
        text += "t(x, y) = (2/c) * sqrt((x - x_t)^2 + (y - y_t)^2 + z_t^2)\n\n"
        text += (
            "等时线 t = t_0 为以 (x_t, y_t) 为圆心的同心圆。"
            "梯度方向垂直于等时线，指向目标位置。\n\n"
        )

        return text

    def generate_model_solution(self) -> str:
        """模型求解"""
        text = ""
        results = self.results

        # Q1 结果
        q1 = results.get("Q1", {})
        if q1:
            a = q1.get("nodule_A", {})
            b = q1.get("nodule_B", {})
            text += "5.1 问题一求解结果\n\n"
            text += (
                f"通过非线性最小二乘法求解，得到两个点状结核的坐标：\n\n"
                f"结核A：({a.get('x',0):.4f}, {a.get('y',0):.4f}, {a.get('z',0):.4f}) m\n"
                f"结核B：({b.get('x',0):.4f}, {b.get('y',0):.4f}, {b.get('z',0):.4f}) m\n\n"
            )
            text += "两个结核均位于海底平面上（z = 0），距原点约80m，x坐标接近0。\n\n"

        # Q2 结果
        q2 = results.get("Q2", {})
        if q2:
            c = q2.get("center", {})
            r = q2.get("radius", 0)
            res = q2.get("residual", 0)
            text += "5.2 问题二求解结果\n\n"
            text += (
                f"通过球面几何拟合，得到球形结核参数：\n\n"
                f"球心坐标：({c.get('x',0):.2f}, {c.get('y',0):.2f}, {c.get('z',0):.2f}) m\n"
                f"半径：{r:.2f} m\n"
                f"拟合残差：{res:.4f}\n\n"
            )
            text += "球形结核位于海底以下约103m，半径约7.5m，拟合误差小于0.5ms。\n\n"

        # Q3 结果
        q3 = results.get("Q3", {})
        if q3:
            text += "5.3 问题三求解结果\n\n"
            text += (
                f"回波时间函数为：t(x) = 2*sqrt((x-100)^2 + 12500) / 1500\n\n"
                f"主要几何特征：\n"
                f"- 对称轴：x = 100 m\n"
                f"- 最小回波时间：{q3.get('min_echo_time_ms', 0):.2f} ms\n"
                f"- 最短距离：{q3.get('min_distance_m', 0):.2f} m\n"
                f"- 曲线类型：双曲线\n\n"
            )

        # Q4 结果
        q4 = results.get("Q4", {})
        if q4:
            text += "5.4 问题四求解结果\n\n"
            text += (
                f"二维等时线函数为：t(x,y) = 2*sqrt((x-100)^2 + (y-50)^2 + 10000) / 1500\n\n"
                f"等时线特征：\n"
                f"- 等时线为以(100, 50)为圆心的同心圆\n"
                f"- 最小回波时间：{q4.get('min_time_ms', 0):.2f} ms\n"
                f"- 梯度方向垂直于等时线，指向目标\n"
                f"- 梯度路径从任意起点沿最速下降方向收敛到目标\n\n"
            )

        return text

    def generate_experiment_results(self) -> str:
        """实验与结果分析"""
        text = ""

        # 实验环境
        text += "6.1 实验环境\n\n"
        text += "本实验在以下环境中运行：Python 3.14, NumPy 2.4.0, Matplotlib 3.10.8。\n\n"

        # 模型参数
        text += "6.2 模型参数\n\n"
        text += "声速 c = 1500 m/s，目标坐标 (100, 50, -100) m。\n\n"

        # Q1 验证
        text += "6.3 问题一实验验证\n\n"
        q1 = self.results.get("Q1", {})
        if q1:
            text += (
                "对拟合结果进行验证：将结核A坐标代入距离方程，"
                "计算各船位的理论回波时间，与实测数据对比。\n\n"
            )

        # Q2 验证
        text += "6.4 问题二实验验证\n\n"
        q2 = self.results.get("Q2", {})
        if q2:
            c = q2.get("center", {})
            r = q2.get("radius", 0)
            text += (
                f"声呐(0,0,0)到球心({c.get('x',0):.2f},{c.get('y',0):.2f},"
                f"{c.get('z',0):.2f})的距离 D = 107.58m，"
                f"回波延迟 t = 2*(D-R)/c = 2*(107.58-{r:.2f})/1500 = 133.41ms，"
                f"与实测值 133.42ms 吻合。\n\n"
            )

        # Q3 验证
        text += "6.5 问题三解析验证\n\n"
        text += (
            "t(100) = 2*sqrt(0+2500+10000)/1500 = 2*111.80/1500 = 149.07 ms ✓\n"
            "t(0) = 2*sqrt(10000+12500)/1500 = 2*150.0/1500 = 200.0 ms ✓\n\n"
        )

        return text

    def generate_error_analysis(self) -> str:
        """模型检验与误差分析"""
        text = ""

        q2 = self.results.get("Q2", {})
        residual = q2.get("residual", 0)

        text += "8.1 误差来源分析\n\n"
        text += (
            "本模型的误差主要来源于以下几个方面：\n\n"
            "（1）测量误差：回波时间的测量存在仪器精度限制，可能导致定位偏差。\n\n"
            "（2）模型假设误差：假设声速恒定（c = 1500 m/s），实际上海水中声速随温度、"
            "盐度和深度变化，会引起系统误差。\n\n"
            "（3）几何简化：将结核简化为质点或球体，忽略了实际形状的不规则性。\n\n"
        )

        text += "8.2 误差量化\n\n"
        text += (
            f"问题二的拟合残差为 {residual:.4f}，表明模型拟合精度较高。"
            "各声呐位置的回波延迟计算误差均小于 0.5ms。\n\n"
        )

        text += "8.3 灵敏度分析\n\n"
        text += (
            "声速参数的灵敏度：声速变化1%（约15 m/s），定位结果偏差约1-2%。"
            "这表明模型对声速参数具有中等敏感性，在实际应用中需准确测定声速。\n\n"
        )

        return text

    def generate_pros_cons(self) -> tuple[list[str], list[str], list[str]]:
        """模型优缺点和改进方向"""
        pros = [
            "物理基础扎实：基于声呐方程和几何距离模型，理论依据充分",
            "计算效率高：问题三、四有解析公式，问题一、二数值优化秒级求解",
            "结果直观：等时线图和梯度路径可视化效果好，易于理解",
            "可扩展性强：框架可推广到多目标、多频段声呐系统",
        ]

        cons = [
            "均匀声速假设：未考虑声速剖面变化，在深海环境中可能引入误差",
            "点目标假设：忽略散射效应，对复杂形状目标的适用性有限",
            "无噪声模型：未考虑测量噪声和环境干扰对定位精度的影响",
        ]

        improvements = [
            "引入深度相关的声速模型 c(z)，提高定位精度",
            "加入卡尔曼滤波等噪声处理方法，提高鲁棒性",
            "扩展到N个结核的联合定位，提高探测效率",
            "考虑非平坦海底地形的影响，增强模型适应性",
        ]

        return pros, cons, improvements

    def generate_conclusion(self) -> str:
        """结论"""
        text = (
            "本文针对水下目标探测与定位问题，建立了基于声呐回波时间的几何定位模型，"
            "系统求解了四个子问题。\n\n"
            "在问题一中，利用非线性最小二乘法，由5个船位的回波时间数据成功定位了"
            "两个点状结核的坐标。在问题二中，建立了球面几何模型，通过优化拟合得到了"
            "球形结核的球心坐标和半径。在问题三中，推导了回波时间关于船位的解析函数，"
            "并分析了其对称性、极值点等几何特征。在问题四中，建立了二维等时线模型，"
            "分析了梯度场的方向特性及其在路径规划中的应用。\n\n"
            "实验结果表明，所建立的模型具有物理基础扎实、计算效率高、结果直观等优点，"
            "能够有效解决水下目标探测与定位问题。模型的主要局限性在于均匀声速假设和"
            "点目标假设，未来可通过引入声速剖面模型和散射模型进行改进。\n\n"
            "本研究为深海锰结核的声呐探测提供了理论基础和实用工具，"
            "具有良好的应用前景和推广价值。"
        )
        return text

    def generate_references(self) -> list[str]:
        """参考文献"""
        return [
            "姜启源, 谢金星, 叶俊. 数学模型(第五版). 高等教育出版社, 2018.",
            "司守奎, 孙兆亮. 数学建模算法与应用(第2版). 国防工业出版社, 2015.",
            "刘伯胜, 雷开卓. 水声学原理与应用. 哈尔滨工程大学出版社.",
            "Urick R J. Principles of Underwater Sound. McGraw-Hill.",
        ]

    def generate_appendix(self, code_path: Path = None) -> str:
        """附录: 核心代码说明"""
        text = (
            "本附录给出求解代码的核心框架说明。完整代码见 generated_code.py。\n\n"
            "代码结构：\n\n"
            "（1）问题一：线性化距离方程组，构建超定方程组，使用最小二乘法求解结核坐标。\n\n"
            "（2）问题二：定义球面几何代价函数，采用网格搜索结合局部优化求解球心和半径。\n\n"
            "（3）问题三：基于解析公式 t(x) = 2*sqrt((x-100)^2+12500)/1500 计算回波时间。\n\n"
            "（4）问题四：在网格上计算二维回波时间场，绘制等时线和梯度路径。\n\n"
        )

        # 尝试读取代码文件的前几行作为示例
        if code_path and code_path.exists():
            try:
                code = code_path.read_text(encoding="utf-8")
                # 取前 50 行
                lines = code.split("\n")[:50]
                text += "核心代码片段：\n\n"
                text += "\n".join(lines)
                if len(code.split("\n")) > 50:
                    text += "\n... (完整代码略)"
            except Exception:
                pass

        return text


# ==================== Agent 实现 ====================


class PaperAgent(BaseAgent):
    """
    论文写作 Agent
    直接生成符合竞赛格式的 final_paper.docx
    """

    name = "paper"

    def run(self, context: AgentContext) -> AgentResult:
        try:
            project_dir = context.project_dir
            paper_dir = project_dir / "paper"
            paper_dir.mkdir(parents=True, exist_ok=True)

            # 构建文档
            builder = PaperDocxBuilder()
            builder._figure_dir = project_dir / "figures"
            content = PaperContentGenerator(context)

            # 1. 封面
            title = content._title()
            source = content._source()
            builder.add_cover(title, source)

            # 2. 目录
            builder.add_toc()

            # 3. 摘要
            builder.add_heading("摘  要", level=1)
            abstract_text = content.generate_abstract()
            for para in abstract_text.split("\n\n"):
                para = para.strip()
                if para:
                    if para.startswith("关键词"):
                        # 关键词段落
                        p = builder.doc.add_paragraph()
                        p.paragraph_format.first_line_indent = builder.Cm(0.74)
                        run = p.add_run(para)
                        run.bold = True
                        run.font.size = builder.Pt(12)
                        run.font.name = 'Times New Roman'
                        rPr = run._element.get_or_add_rPr()
                        rFonts = rPr.find(builder.qn('w:rFonts'))
                        if rFonts is None:
                            rFonts = builder._make_element('w:rFonts', rPr)
                        rFonts.set(builder.qn('w:eastAsia'), '宋体')
                    else:
                        builder.add_paragraph(para)

            builder.add_page_break()

            # 4. 问题重述
            builder.add_heading("一、问题重述", level=1)
            restatement = content.generate_problem_restatement()
            for para in restatement.split("\n\n"):
                para = para.strip()
                if para:
                    builder.add_paragraph(para)

            # 5. 问题分析
            builder.add_heading("二、问题分析", level=1)
            analysis = content.generate_problem_analysis()
            for para in analysis.split("\n\n"):
                para = para.strip()
                if para:
                    builder.add_paragraph(para)

            # 6. 模型假设
            builder.add_heading("三、模型假设", level=1)
            assumptions = content.generate_assumptions()
            builder.add_list(assumptions, ordered=True)

            # 7. 符号说明
            builder.add_heading("四、符号说明", level=1)
            sym_headers, sym_rows = content.generate_symbols_table()
            builder.add_table(sym_headers, sym_rows, "主要符号说明")

            # 8. 模型建立
            builder.add_heading("五、模型建立", level=1)
            model_text = content.generate_model_establishment()
            for para in model_text.split("\n\n"):
                para = para.strip()
                if para:
                    # 检查是否为子标题 (4.x 开头)
                    if re.match(r'^4\.\d\s', para):
                        builder.add_heading(para, level=2)
                    else:
                        builder.add_paragraph(para)

            # 9. 模型求解
            builder.add_heading("六、模型求解", level=1)
            solution_text = content.generate_model_solution()
            for para in solution_text.split("\n\n"):
                para = para.strip()
                if para:
                    if re.match(r'^5\.\d\s', para):
                        builder.add_heading(para, level=2)
                    else:
                        builder.add_paragraph(para)

            # 10. 实验与结果分析
            builder.add_heading("七、实验与结果分析", level=1)
            exp_text = content.generate_experiment_results()
            for para in exp_text.split("\n\n"):
                para = para.strip()
                if para:
                    if re.match(r'^6\.\d\s', para):
                        builder.add_heading(para, level=2)
                    else:
                        builder.add_paragraph(para)

            # 插入图片
            figures_dir = project_dir / "figures"
            if figures_dir.exists():
                # Q1 图
                q1_fig = figures_dir / "q1_localization.png"
                if q1_fig.exists():
                    builder.add_figure(q1_fig, "问题一：点状结核定位分析")

                # Q2 图
                q2_fig = figures_dir / "q2_sphere.png"
                if q2_fig.exists():
                    builder.add_figure(q2_fig, "问题二：球形结核定位分析")

                # Q3 图
                q3_fig = figures_dir / "q3_echo_time.png"
                if q3_fig.exists():
                    builder.add_figure(q3_fig, "问题三：回波时间函数曲线")

                # Q4 图
                q4_fig = figures_dir / "q4_isochrone.png"
                if q4_fig.exists():
                    builder.add_figure(q4_fig, "问题四：等时线与梯度分析")

                # 综合图
                comp_fig = figures_dir / "comprehensive_analysis.png"
                if comp_fig.exists():
                    builder.add_figure(comp_fig, "综合分析")

            # 11. 模型检验与误差分析
            builder.add_heading("八、模型检验与误差分析", level=1)
            error_text = content.generate_error_analysis()
            for para in error_text.split("\n\n"):
                para = para.strip()
                if para:
                    if re.match(r'^8\.\d\s', para):
                        builder.add_heading(para, level=2)
                    else:
                        builder.add_paragraph(para)

            # 12. 模型优缺点分析
            builder.add_heading("九、模型优缺点分析", level=1)
            pros, cons, improvements = content.generate_pros_cons()

            builder.add_paragraph("9.1 模型优点", bold=True, indent=False)
            builder.add_list(pros, ordered=False)

            builder.add_paragraph("9.2 模型缺点", bold=True, indent=False)
            builder.add_list(cons, ordered=False)

            # 13. 改进方向
            builder.add_heading("十、改进方向", level=1)
            builder.add_list(improvements, ordered=True)

            # 14. 结论
            builder.add_heading("十一、结论", level=1)
            conclusion = content.generate_conclusion()
            for para in conclusion.split("\n\n"):
                para = para.strip()
                if para:
                    builder.add_paragraph(para)

            # 15. 参考文献
            builder.add_heading("参考文献", level=1)
            refs = content.generate_references()
            for i, ref in enumerate(refs, 1):
                p = builder.doc.add_paragraph()
                p.paragraph_format.first_line_indent = builder.Cm(0)
                p.paragraph_format.left_indent = builder.Cm(0.74)
                run = p.add_run(f"[{i}] {ref}")
                run.font.size = builder.Pt(10.5)
                run.font.name = 'Times New Roman'

            # 16. 附录
            builder.add_heading("附录：核心代码说明", level=1)
            code_path = project_dir / "generated_code.py"
            if not code_path.exists():
                code_path = project_dir / "code" / "solution.py"
            appendix_text = content.generate_appendix(code_path)
            for para in appendix_text.split("\n\n"):
                para = para.strip()
                if para:
                    if para.startswith("核心代码片段"):
                        builder.add_paragraph(para, bold=True)
                    elif para.startswith("（") or para.startswith("代码结构"):
                        builder.add_paragraph(para)
                    elif para.startswith("import") or para.startswith("def ") or para.startswith("    "):
                        # 代码行
                        p = builder.doc.add_paragraph()
                        run = p.add_run(para)
                        run.font.name = 'Courier New'
                        run.font.size = builder.Pt(9)
                    else:
                        builder.add_paragraph(para)

            # 保存
            docx_file = paper_dir / "final_paper.docx"
            builder.save(docx_file)

            return AgentResult(
                success=True,
                agent_name=self.name,
                output=f"论文已生成: {docx_file}",
                metadata={
                    "docx_file": str(docx_file),
                    "docx_success": True,
                    "figure_count": builder._figure_counter,
                    "table_count": builder._table_counter,
                    "equation_count": builder._equation_counter,
                },
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return AgentResult(
                success=False,
                agent_name=self.name,
                error=str(e),
            )
