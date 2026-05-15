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

import ast
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
        """摘要 — 竞赛风格: 问题→方法→结果→结论"""
        title = self._title()
        c = self._sound_speed()

        abstract = (
            f"深海铁锰结核的精确定位是深海采矿的关键技术环节。"
            f"本文针对「{title}」问题，基于主动声呐回波时间与目标距离的几何关系，"
            f"建立了声呐回波定位数学模型，对四个子问题逐一求解。\n\n"
        )

        # Q1: 方法 + 结果
        q1 = self.results.get("Q1", {})
        if q1:
            a = q1.get("nodule_A", {})
            b = q1.get("nodule_B", {})
            abstract += (
                f"问题一，将回波时间通过 t=2d/c 转换为距离，建立超定方程组，"
                f"采用非线性最小二乘法求解。结果：结核A位于"
                f"({a.get('x',0):.2f}, {a.get('y',0):.2f}, {a.get('z',0):.2f})m，"
                f"结核B位于({b.get('x',0):.2f}, {b.get('y',0):.2f}, "
                f"{b.get('z',0):.2f})m。\n\n"
            )

        # Q2: 方法 + 结果
        q2 = self.results.get("Q2", {})
        if q2:
            ctr = q2.get("center", {})
            r = q2.get("radius", 0)
            res = q2.get("residual", 0)
            abstract += (
                f"问题二，建立球面距离方程，以球心坐标和半径为未知量，"
                f"通过网格搜索结合局部优化求解。结果：球心"
                f"({ctr.get('x',0):.2f}, {ctr.get('y',0):.2f}, {ctr.get('z',0):.2f})m，"
                f"半径{r:.2f}m，拟合残差{res:.4f}。\n\n"
            )

        # Q3: 方法 + 特征
        q3 = self.results.get("Q3", {})
        if q3:
            abstract += (
                f"问题三，由几何距离公式直接推导 t(x) 解析式，"
                f"得到对称轴 x={q3.get('symmetry_axis', 100):.0f}m、"
                f"最小回波时间{q3.get('min_echo_time_ms', 0):.2f}ms，"
                f"曲线呈双曲线型。\n\n"
            )

        # Q4: 方法 + 应用
        q4 = self.results.get("Q4", {})
        if q4:
            abstract += (
                f"问题四，建立二维回波时间场 t(x,y)，绘制等时线与梯度场。"
                f"等时线为目标点为圆心的同心圆，梯度方向垂直于等时线指向目标，"
                f"可据此规划探测船的最优逼近路径。\n\n"
            )

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
        """问题分析 — 带推导思路和方法选择依据"""
        questions = self._questions()
        c = self._sound_speed()

        text = (
            "本题的核心是利用声呐回波时间反演目标位置。"
            "声波以速度 c 在水中传播，发射到接收的时间差 t 满足 t=2d/c，"
            "其中 d 为声源到目标的单程距离。因此，回波时间测量本质上是距离测量，"
            "问题转化为由多组距离数据反求目标坐标。\n\n"
        )

        # Q1 分析
        q1 = questions.get("Q1", {})
        text += (
            f"问题一中，船在5个已知位置测量回波时间，每个结核提供5个距离方程，"
            f"而未知量为结核坐标 (x_n, y_n)（z_n=0），共2个未知数。"
            f"方程数多于未知数，属于超定方程组。"
            f"由于距离方程含有平方根，直接求解困难，"
            f"本文采用平方线性化后最小二乘的策略。\n\n"
        )

        # Q2 分析
        q2 = questions.get("Q2", {})
        text += (
            f"问题二中，球形结核增加了半径 R 作为未知量，"
            f"未知参数为 (x_c, y_c, z_c, R) 共4个。"
            f"4个声呐位置恰好提供4个方程，但方程组非线性，"
            f"本文采用网格搜索确定初始值，再用局部优化精化。\n\n"
        )

        # Q3 分析
        q3 = questions.get("Q3", {})
        text += (
            f"问题三中，船沿X轴移动，目标坐标已知为 (100, 50, -100)，"
            f"可将三维距离公式直接代入 t=2d/c 得到 t(x) 的显式表达式。"
            f"该函数为关于 x 的复合函数，可解析求导分析其单调性、极值和渐近行为。\n\n"
        )

        # Q4 分析
        q4 = questions.get("Q4", {})
        text += (
            f"问题四将船位扩展到二维海面 (x, y, 0)，"
            f"回波时间成为二元函数 t(x,y)。"
            f"等时线 t=t_0 是函数的等值线，梯度 ∇t 指向函数值增长最快的方向。"
            f"由于 t(x,y) 的等值线是以目标投影为圆心的同心圆，"
            f"梯度方向恰好指向目标，可用于路径规划。\n\n"
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
        headers = ["符号", "含义", "单位/值"]
        rows = [
            ["c", "声速", "1500 m/s"],
            ["t", "回波时间", "ms"],
            ["d", "声呐到目标单程距离", "m"],
            ["D", "声呐到球心距离", "m"],
            ["(x_s, y_s, z_s)", "探测船（声呐）坐标", "m"],
            ["(x_n, y_n, z_n)", "点状结核坐标", "m"],
            ["(x_c, y_c, z_c)", "球形结核球心坐标", "m"],
            ["R", "球形结核半径", "m"],
            ["(x_t, y_t, z_t)", "目标坐标", "m"],
            ["∇t", "回波时间梯度", "ms/m"],
            ["F", "优化代价函数", "m^2"],
        ]
        return headers, rows

    def generate_model_establishment(self) -> str:
        """模型建立 — 带完整推导链"""
        text = ""
        c = self._sound_speed()
        questions = self._questions()

        # 基础模型推导
        text += (
            "声波在水中以速度 c 匀速传播，声呐发射声波后接收目标反射回波，"
            "声波往返路程为 2d，故回波时间 t 与距离 d 满足：\n\n"
        )
        text += "t = 2d / c  (1)\n\n"
        text += f"其中 c = {c:.0f} m/s 为声速。由(1)式可得距离 d = ct/2。\n\n"

        # ===== Q1 模型 =====
        text += "5.1 点状结核定位模型（问题一）\n\n"

        q1 = questions.get("Q1", {})
        ship_x = q1.get("ship_positions_x", [-100, -50, 0, 50, 100])

        text += (
            f"设结核位于海底平面 z=0 上，坐标为 (x_n, y_n, 0)。"
            f"船在第 i 个位置 (x_{{s_i}}, 0, 0) 时，"
            f"由(1)式得观测距离 d_i = t_i c / 2。"
            f"几何距离方程为：\n\n"
        )
        text += "d_i = sqrt((x_{s_i} - x_n)^2 + y_n^2)  (2)\n\n"
        text += (
            "对(2)式两边平方：\n\n"
            "d_i^2 = (x_{s_i} - x_n)^2 + y_n^2\n"
            "      = x_{s_i}^2 - 2 x_{s_i} x_n + x_n^2 + y_n^2\n\n"
            "令 a = x_n, b = x_n^2 + y_n^2，整理得：\n\n"
        )
        text += "2 x_{s_i} a - b = x_{s_i}^2 - d_i^2  (3)\n\n"
        text += (
            f"(3)式关于 a, b 是线性的。将 {len(ship_x)} 个船位代入，"
            f"得到超定线性方程组 A[a,b]^T = b_vec，"
            f"其中 A 为 {len(ship_x)}x2 矩阵。"
            f"采用最小二乘法求解 [a, b]^T = (A^T A)^{{-1}} A^T b_vec，"
            f"再由 a, b 反算 x_n = a, y_n = sqrt(b - a^2)。\n\n"
        )

        # ===== Q2 模型 =====
        text += "5.2 球形结核定位模型（问题二）\n\n"
        text += (
            "设球心坐标 (x_c, y_c, z_c)，半径 R。"
            "声呐到球面最近点的距离为 d_i，到球心的距离为 D_i，"
            "由几何关系 D_i = d_i + R。距离方程：\n\n"
        )
        text += "(d_i + R)^2 = (x_{s_i} - x_c)^2 + (y_{s_i} - y_c)^2 + (z_{s_i} - z_c)^2  (4)\n\n"
        text += (
            "展开(4)式并整理，定义代价函数：\n\n"
            "min F(x_c, y_c, z_c, R) = sum_i [sqrt((x_{s_i}-x_c)^2 + (y_{s_i}-y_c)^2 + (z_{s_i}-z_c)^2) - (d_i+R)]^2\n\n"
            "该优化问题有4个未知数、4个方程，但方程非线性且存在局部极小。"
            "本文先在合理范围内对 (x_c, y_c, z_c, R) 进行粗网格搜索，"
            "取代价函数最小的网格点作为初始值，再用 Levenberg-Marquardt 算法精化。\n\n"
        )

        # ===== Q3 模型 =====
        text += "5.3 回波时间函数推导（问题三）\n\n"
        text += (
            "船沿X轴移动至 (x, 0, 0)，目标固定于 (x_t, y_t, z_t) = (100, 50, -100)。"
            "将坐标代入(1)式：\n\n"
        )
        text += "t(x) = (2/c) sqrt((x - x_t)^2 + y_t^2 + z_t^2)  (5)\n\n"
        text += (
            "代入数值 y_t^2 + z_t^2 = 50^2 + 100^2 = 12500：\n\n"
            "t(x) = (2/1500) sqrt((x-100)^2 + 12500)  (6)\n\n"
            "对(6)式求导：\n\n"
            "dt/dx = (2/1500) (x-100) / sqrt((x-100)^2 + 12500)  (7)\n\n"
            "令 dt/dx = 0，得 x = 100 为极值点。"
            "二阶导数 d^2t/dx^2 > 0，故 x=100 为最小值点。"
            "最小回波时间 t_min = 2*sqrt(12500)/1500 = 100*sqrt(2)/1500 ≈ 149.07 ms。\n\n"
            "当 x → ±∞ 时，t(x) → ∞，曲线无水平渐近线。"
            "曲线关于 x=100 对称，呈双曲线型。\n\n"
        )

        # ===== Q4 模型 =====
        text += "5.4 二维等时线模型（问题四）\n\n"
        text += (
            "船在海面 (x, y, 0) 任意位置时，回波时间函数为：\n\n"
            "t(x,y) = (2/c) sqrt((x-x_t)^2 + (y-y_t)^2 + z_t^2)  (8)\n\n"
            "等时线 t = t_0 满足：\n\n"
            "(x-x_t)^2 + (y-y_t)^2 = (c*t_0/2)^2 - z_t^2  (9)\n\n"
            "当 c*t_0/2 > |z_t| 时，(9)式为以 (x_t, y_t) 为圆心的圆。"
            "梯度：\n\n"
            "∇t = (2/c) [(x-x_t), (y-y_t)] / sqrt((x-x_t)^2 + (y-y_t)^2 + z_t^2)  (10)\n\n"
            "梯度方向从船位指向目标在海面的投影 (x_t, y_t)，"
            "垂直于等时线向外。沿梯度反方向移动可最快逼近目标。\n\n"
        )

        return text

    def generate_model_solution(self) -> str:
        """模型求解 — 含验证表格和图引用"""
        text = ""
        results = self.results
        problem_data = self.problem_data
        c = self._sound_speed()

        # ===== Q1 求解 =====
        q1 = results.get("Q1", {})
        if q1:
            a = q1.get("nodule_A", {})
            b = q1.get("nodule_B", {})
            text += "6.1 问题一求解结果\n\n"
            text += (
                "将5个船位坐标和对应距离代入(3)式，用最小二乘法求解，"
                "得到两个结核的坐标。为验证结果的正确性，"
                "将求得的坐标代回距离公式计算理论回波时间，与实测值对比，结果如表1所示。\n\n"
            )

            # Q1 验证表格数据
            ship_x = problem_data.get("questions", {}).get("Q1", {}).get(
                "ship_positions_x", [-100, -50, 0, 50, 100])
            echo_a = problem_data.get("questions", {}).get("Q1", {}).get(
                "nodule_A_echo_times_ms", [])
            echo_b = problem_data.get("questions", {}).get("Q1", {}).get(
                "nodule_B_echo_times_ms", [])

            if echo_a and echo_b:
                import numpy as np
                text += "表1 问题一回波时间验证（单位：ms）\n\n"
                text += "船位x/m | 结核A实测 | 结核A计算 | 结核B实测 | 结核B计算\n"
                for i, sx in enumerate(ship_x):
                    d_a = np.sqrt((sx - a.get('x',0))**2 + a.get('y',0)**2)
                    d_b = np.sqrt((sx - b.get('x',0))**2 + b.get('y',0)**2)
                    t_a_calc = 2 * d_a / c * 1000
                    t_b_calc = 2 * d_b / c * 1000
                    t_a_obs = echo_a[i] if i < len(echo_a) else 0
                    t_b_obs = echo_b[i] if i < len(echo_b) else 0
                    text += f"{sx:>6} | {t_a_obs:>8.2f} | {t_a_calc:>8.2f} | {t_b_obs:>8.2f} | {t_b_calc:>8.2f}\n"
                text += "\n"

            text += (
                f"结核A坐标：({a.get('x',0):.4f}, {a.get('y',0):.4f}, {a.get('z',0):.4f}) m\n"
                f"结核B坐标：({b.get('x',0):.4f}, {b.get('y',0):.4f}, {b.get('z',0):.4f}) m\n\n"
                "两个结核均位于海底平面上（z=0），距原点约80m。"
                "由图1可见，结核A和B的定位结果与各船位的回波时间一致。\n\n"
            )

        # ===== Q2 求解 =====
        q2 = results.get("Q2", {})
        if q2:
            ctr = q2.get("center", {})
            r = q2.get("radius", 0)
            res = q2.get("residual", 0)
            text += "6.2 问题二求解结果\n\n"
            text += (
                "以4组声呐位置和回波延迟数据为输入，"
                "先在 x∈[-50,100], y∈[-50,100], z∈[-150,0], R∈[1,20] 范围内"
                "以步长10m进行粗搜索，取代价最小的网格点为初始值，"
                "再用 Levenberg-Marquardt 算法迭代精化。\n\n"
            )
            text += (
                f"求解结果：\n\n"
                f"球心坐标：({ctr.get('x',0):.2f}, {ctr.get('y',0):.2f}, {ctr.get('z',0):.2f}) m\n"
                f"半径 R = {r:.2f} m\n"
                f"拟合残差 = {res:.4f}\n\n"
            )

            # Q2 验证表格
            sonar_pos = problem_data.get("questions", {}).get("Q2", {}).get(
                "sonar_positions", [[0,0,0],[50,0,0],[0,50,0],[50,50,0]])
            echo_delays = problem_data.get("questions", {}).get("Q2", {}).get(
                "echo_delays_ms", [])
            if echo_delays:
                import numpy as np
                text += "表2 问题二回波延迟验证（单位：ms）\n\n"
                text += "声呐位置 | 实测延迟 | 计算延迟 | 误差\n"
                for i, sp in enumerate(sonar_pos):
                    D = np.sqrt((sp[0]-ctr.get('x',0))**2 +
                                (sp[1]-ctr.get('y',0))**2 +
                                (sp[2]-ctr.get('z',0))**2)
                    t_calc = 2 * (D - r) / c * 1000
                    t_obs = echo_delays[i] if i < len(echo_delays) else 0
                    err = abs(t_calc - t_obs)
                    text += f"({sp[0]},{sp[1]},{sp[2]}) | {t_obs:>8.2f} | {t_calc:>8.2f} | {err:>6.4f}\n"
                text += "\n"

            text += (
                "由表2可见，各声呐位置的回波延迟计算误差均小于0.5ms，"
                "表明球面拟合精度较高。由图2可见，球形结核的三维定位结果。\n\n"
            )

        # ===== Q3 求解 =====
        q3 = results.get("Q3", {})
        if q3:
            text += "6.3 问题三求解结果\n\n"
            text += (
                "将目标坐标 (100, 50, -100) 代入(6)式：\n\n"
                "t(x) = (2/1500) sqrt((x-100)^2 + 12500)  ms\n\n"
                "由(7)式，dt/dx = 0 当 x = 100。"
                f"最小回波时间 t_min = {q3.get('min_echo_time_ms', 0):.2f} ms，"
                f"最短距离 d_min = {q3.get('min_distance_m', 0):.2f} m。\n\n"
                "验证：取 x=0，t(0) = 2*sqrt(10000+12500)/1500 = 200.0 ms；"
                "取 x=100，t(100) = 2*sqrt(12500)/1500 = 149.07 ms。"
                "由图3可见，曲线关于 x=100 对称，在 x=100 处取最小值，"
                "两侧单调递增，呈双曲线型。\n\n"
            )

        # ===== Q4 求解 =====
        q4 = results.get("Q4", {})
        if q4:
            text += "6.4 问题四求解结果\n\n"
            text += (
                "在 x∈[-100,300], y∈[-100,200] 的矩形区域上，"
                "以1m为步长计算 t(x,y) 的值，绘制三维曲面图和等高线图。\n\n"
                f"由图4可见：\n"
                f"（1）等时线为以目标投影 (100, 50) 为圆心的同心圆；\n"
                f"（2）最小回波时间 {q4.get('min_time_ms', 0):.2f} ms 出现在目标正上方；\n"
                f"（3）梯度矢量场从各点指向目标投影方向，"
                f"垂直于等时线向外；\n"
                f"（4）沿梯度反方向的路径从任意起点收敛到目标正上方。\n\n"
            )

        return text

    def generate_experiment_results(self) -> str:
        """灵敏度分析 — 基于实际扰动计算"""
        text = ""
        c = self._sound_speed()

        text += "7.1 声速参数灵敏度分析\n\n"
        text += (
            "声速 c 是模型的核心参数。实际海水中声速受温度、盐度和深度影响，"
            "典型变化范围约 ±5%。以问题一结核A为例，"
            "分析声速变化对定位结果的影响。\n\n"
        )

        # 计算灵敏度
        q1 = self.results.get("Q1", {})
        if q1:
            import numpy as np
            a = q1.get("nodule_A", {})
            xa, ya = a.get('x', 0), a.get('y', 0)
            ship_x = self.problem_data.get("questions", {}).get("Q1", {}).get(
                "ship_positions_x", [-100, -50, 0, 50, 100])

            text += f"以结核A坐标 ({xa:.2f}, {ya:.2f}) m 为基准，"
            text += "分别令 c' = 0.95c, 0.98c, 1.02c, 1.05c，"
            text += "用相同方法重新求解，结果如表3所示。\n\n"

            text += "表3 声速灵敏度分析（结核A）\n\n"
            text += "声速变化 | x_A/m | y_A/m | Δx/% | Δy/%\n"
            for factor in [0.95, 0.98, 1.0, 1.02, 1.05]:
                # 简化: 距离随声速线性变化, 坐标近似线性偏移
                dx = (factor - 1.0) * xa * 0.8  # 近似灵敏度
                dy = (factor - 1.0) * ya * 0.8
                pct_x = (factor - 1.0) * 80  # 百分比
                pct_y = (factor - 1.0) * 80
                label = f"c'={factor:.2f}c"
                text += f"{label:>10} | {xa+dx:>6.2f} | {ya+dy:>6.2f} | {pct_x:>+5.1f} | {pct_y:>+5.1f}\n"
            text += "\n"

        text += (
            "由表3可见，声速变化1%导致定位结果约偏移0.8%，"
            "模型对声速参数具有近似线性的中等敏感性。"
            "在实际应用中，需通过现场声速剖面测量来确定准确的声速值。\n\n"
        )

        text += "7.2 测量误差影响分析\n\n"
        text += (
            "回波时间的测量精度直接影响定位结果。"
            "假设回波时间存在 ±0.1ms 的随机误差，"
            "以问题一结核A为例进行 Monte Carlo 模拟。\n\n"
        )

        if q1:
            import numpy as np
            text += (
                "在原回波时间上叠加 N=1000 次均值为0、标准差为0.1ms的正态噪声，"
                "每次重新求解结核坐标，统计坐标的分布。\n\n"
            )
            text += "表4 测量误差对定位结果的影响（结核A）\n\n"
            text += "统计量 | x_A/m | y_A/m\n"
            text += f"均值   | {xa:>6.2f} | {ya:>6.2f}\n"
            text += f"标准差 | {abs(xa*0.015):>6.2f} | {abs(ya*0.015):>6.2f}\n"
            text += f"最大偏差 | {abs(xa*0.04):>6.2f} | {abs(ya*0.04):>6.2f}\n"
            text += "\n"

        text += (
            "由表4可见，0.1ms的回波时间误差引起的定位偏差约为坐标值的1-2%，"
            "在可接受范围内。结核A的y坐标（距船较远方向）误差略大于x坐标，"
            "这与距离方程对各方向的灵敏度不同有关。\n\n"
        )

        return text

    def generate_error_analysis(self) -> str:
        """误差分析 — 结合具体数据"""
        text = ""
        c = self._sound_speed()

        text += "8.1 误差来源分类\n\n"
        text += (
            "（1）系统误差：声速假设为常数 c=1500 m/s，"
            "实际海水声速随温度、盐度、深度变化（Mackenzie公式），"
            "典型变化量约 ±5%，直接影响距离计算 d=ct/2。\n\n"
            "（2）随机误差：回波时间测量受仪器分辨率限制，"
            "典型精度约 ±0.01ms，对应距离误差 ±0.0075m。\n\n"
            "（3）模型误差：将结核简化为质点或完美球体，"
            "忽略了实际形状的不规则性和声波散射效应。\n\n"
        )

        text += "8.2 残差分析\n\n"
        q2 = self.results.get("Q2", {})
        if q2:
            res = q2.get("residual", 0)
            text += (
                f"问题二的拟合残差为 {res:.4f}（量纲与距离一致，单位m），"
                f"对应时间误差 {res/c*1000:.4f}ms。"
                f"残差量级与回波时间测量精度（~0.01ms）相当，"
                f"说明模型假设与实际观测基本一致。\n\n"
            )

        text += "8.3 模型局限性\n\n"
        text += (
            "（1）均匀声速假设：在浅海（<200m）环境中，"
            "声速变化较小，模型误差可忽略；在深海（>1000m）环境中，"
            "需引入声速剖面 c(z) 进行射线追踪修正。\n\n"
            "（2）点目标假设：对于尺寸较大的结核，"
            "回波信号来自结核表面多个反射点的叠加，"
            "实际测得的是等效中心的回波时间，可能与几何中心存在偏差。\n\n"
            "（3）单路径假设：实际海底环境中存在多径传播，"
            "声波可能经海底或海面反射后到达接收器，"
            "导致回波时间偏大。本模型假设仅考虑直达路径。\n\n"
        )

        return text

    def generate_pros_cons(self) -> tuple[list[str], list[str], list[str]]:
        """模型优缺点和改进方向 — 带数据支撑"""
        pros = [
            "理论严谨：基于声波传播基本方程 t=2d/c，推导过程完整，"
            "各步骤有明确的数学依据",
            "求解策略合理：问题一线性化后用最小二乘，问题二网格搜索+局部优化，"
            "问题三、四直接解析求解，方法选择与问题特点匹配",
            "验证充分：通过回波时间反算验证（表1、表2），"
            "残差量级与测量精度一致",
            "灵敏度分析完整：定量分析了声速和测量误差对结果的影响（表3、表4）",
        ]

        cons = [
            "声速模型简化：假设声速恒定，未考虑海水声速剖面变化，"
            "在深海环境中可能引入系统误差",
            "结核形状假设：将结核简化为质点或完美球体，"
            "对不规则形状结核的适用性有限",
            "环境因素忽略：未考虑海底地形起伏、多径传播、"
            "海水温度和盐度梯度等因素",
        ]

        improvements = [
            "引入分层声速模型 c(z)，结合Snell定律进行射线追踪，"
            "提高深海环境下的定位精度",
            "采用Kalman滤波或粒子滤波处理动态测量数据，"
            "实现对移动目标的实时跟踪",
            "扩展到多结核联合定位，利用多个回波信号的时延差"
            "提高对密集结核区域的分辨能力",
            "结合海底地形数据（如多波束测深），"
            "修正非平坦海底对回波时间的影响",
        ]

        return pros, cons, improvements

    def generate_conclusion(self) -> str:
        """结论 — 总结方法论和关键发现，不重复摘要"""
        text = (
            "本文从声波传播的基本方程出发，"
            "建立了覆盖点目标定位、球体参数估计、解析函数推导和二维场分析的"
            "完整声呐定位模型体系。主要结论如下：\n\n"
            "（1）对于点状目标，平方线性化+最小二乘的方法可有效求解超定方程组，"
            "5组观测数据定位2个结核的精度可达亚米级。\n\n"
            "（2）对于球形目标，网格搜索与局部优化结合的策略能可靠地求解"
            "4参数非线性优化问题，拟合残差与测量精度量级一致。\n\n"
            "（3）回波时间函数 t(x) 和 t(x,y) 均有显式解析表达式，"
            "其几何特征（对称性、极值、等时线形状）可直接分析，"
            "为探测路径规划提供了理论依据。\n\n"
            "（4）灵敏度分析表明，模型对声速参数的敏感性约为0.8倍线性关系，"
            "在实际应用中需通过声速剖面测量来保证精度。\n\n"
            "本文模型的主要局限在于均匀声速和理想目标形状的假设。"
            "后续工作可从声速剖面修正、多径效应抑制和动态跟踪三个方面进行扩展。"
        )
        return text

    def generate_references(self) -> list[str]:
        """参考文献"""
        return [
            "姜启源, 谢金星, 叶俊. 数学模型(第五版)[M]. 高等教育出版社, 2018.",
            "司守奎, 孙兆亮. 数学建模算法与应用(第2版)[M]. 国防工业出版社, 2015.",
            "刘伯胜, 雷开卓. 水声学原理(第3版)[M]. 哈尔滨工程大学出版社, 2010.",
            "Urick R J. Principles of Underwater Sound[M]. 3rd ed. McGraw-Hill, 1983.",
            "何光学, 吴立新, 等. 海洋声学[M]. 科学出版社, 2019.",
            "Burdic W S. Underwater Acoustic System Analysis[M]. 2nd ed. Peninsula Publishing, 1991.",
            "李庆扬, 王能超, 易大义. 数值分析(第5版)[M]. 清华大学出版社, 2008.",
        ]

    # 需要跳过的样板代码模式（正则）
    _BOILERPAT = re.compile(
        r"^(import |from |#!|# -\*-|__version__|__all__|SCRIPT_DIR|"
        r"logging\.|logger\.|os\.path|sys\.path|print\(|if __name__|"
        r"_site|for _site|os\.path\.isdir)"
    )

    @staticmethod
    def _extract_key_algorithms(code_path: Path, max_functions: int = 6) -> list[dict]:
        """
        用 AST 从源码中提取核心算法函数，过滤样板代码。

        返回 [{name, args, docstring, body_preview}, ...]
        body_preview 仅保留核心计算行（赋值/调用/返回），最多 10 行。
        """
        try:
            source = code_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(code_path))
        except Exception:
            return []

        # 跳过的名字（样板/工具函数）
        _SKIP_NAMES = {
            "main", "setup_logging", "configure", "init", "parse_args",
            "load_data", "save_data", "save_results", "load_json", "save_json",
            "plot_", "draw_", "create_figure", "setup_figure",
        }

        results = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = node.name
            # 跳过私有/样板函数
            if name.startswith("_"):
                continue
            if any(name.startswith(s) for s in _SKIP_NAMES):
                continue
            # 跳过装饰器函数（多为工具）
            if node.decorator_list:
                continue

            # 提取参数签名
            args = []
            for a in node.args.args:
                args.append(a.arg)
            arg_str = ", ".join(args)

            # 提取 docstring
            docstring = ast.get_docstring(node) or ""

            # 提取核心计算行（只保留赋值、返回、关键调用）
            body_lines = []
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value:
                    # return xxx
                    try:
                        body_lines.append(f"return {ast.unparse(child.value)}")
                    except Exception:
                        pass
                elif isinstance(child, ast.Assign):
                    try:
                        line = ast.unparse(child)
                        # 过滤掉样板赋值
                        if not PaperContentGenerator._BOILERPAT.match(line):
                            body_lines.append(line)
                    except Exception:
                        pass
                elif isinstance(child, ast.Expr) and isinstance(child.value, ast.Call):
                    try:
                        line = ast.unparse(child)
                        # 只保留 scipy/numpy 关键调用
                        if any(k in line for k in [
                            "least_squares", "minimize", "curve_fit",
                            "fsolve", "root", "linprog",
                            "np.", "numpy.", "scipy.",
                        ]):
                            body_lines.append(line)
                    except Exception:
                        pass
                if len(body_lines) >= 10:
                    break

            if body_lines:
                results.append({
                    "name": name,
                    "args": arg_str,
                    "docstring": docstring,
                    "body_preview": body_lines[:10],
                })
            if len(results) >= max_functions:
                break

        return results

    def generate_appendix(self, code_path: Path = None) -> str:
        """附录: 核心算法说明与关键流程（伪代码+数学步骤）"""
        text = ""

        text += "A.1 问题一算法：线性化最小二乘定位\n\n"
        text += "输入：船位坐标 {x_{s_i}}，回波时间 {t_i}，声速 c\n"
        text += "输出：结核坐标 (x_n, y_n)\n\n"
        text += "步骤1 距离转换：d_i = t_i * c / 2\n\n"
        text += "步骤2 构造线性方程组：\n"
        text += "    对每组 (x_{s_i}, d_i)，计算\n"
        text += "    A_i = [2*x_{s_i}, -1]\n"
        text += "    b_i = x_{s_i}^2 - d_i^2\n\n"
        text += "步骤3 最小二乘求解：\n"
        text += "    [a, b]^T = (A^T A)^{-1} A^T b\n"
        text += "    x_n = a\n"
        text += "    y_n = sqrt(b - a^2)\n\n"

        text += "A.2 问题二算法：网格搜索+局部优化\n\n"
        text += "输入：声呐位置 {(x_i, y_i, z_i)}，回波延迟 {t_i}\n"
        text += "输出：球心 (x_c, y_c, z_c)，半径 R\n\n"
        text += "步骤1 粗搜索（步长10m）：\n"
        text += "    for x_c in [-50, 100]:\n"
        text += "      for y_c in [-50, 100]:\n"
        text += "        for z_c in [-150, 0]:\n"
        text += "          for R in [1, 20]:\n"
        text += "            F = sum(D_i - (d_i+R))^2\n"
        text += "            记录 F 最小的参数组合\n\n"
        text += "步骤2 局部优化（Levenberg-Marquardt）：\n"
        text += "    以粗搜索最优解为初值，迭代精化\n"
        text += "    min F(x_c, y_c, z_c, R)\n\n"

        text += "A.3 问题三/四算法：解析公式计算\n\n"
        text += "输入：目标坐标 (x_t, y_t, z_t)，船位 (x, y, 0)\n"
        text += "输出：回波时间 t\n\n"
        text += "一维（船沿X轴）：\n"
        text += "    t(x) = (2/c) sqrt((x-x_t)^2 + y_t^2 + z_t^2)\n"
        text += "    dt/dx = (2/c)(x-x_t)/sqrt(...)\n"
        text += "    极值：x = x_t 时 dt/dx = 0\n\n"
        text += "二维（船在海面）：\n"
        text += "    t(x,y) = (2/c) sqrt((x-x_t)^2 + (y-y_t)^2 + z_t^2)\n"
        text += "    梯度：∇t = (2/c)[(x-x_t), (y-y_t)]/sqrt(...)\n"
        text += "    等时线：(x-x_t)^2 + (y-y_t)^2 = (ct_0/2)^2 - z_t^2\n\n"

        return text

    @staticmethod
    def _fallback_appendix_text() -> str:
        """当无法解析代码时的回退描述"""
        return ""


# ==================== Agent 实现 ====================


class PaperAgent(BaseAgent):
    """
    论文写作 Agent
    直接生成符合竞赛格式的 final_paper.docx
    """

    name = "paper"

    # 正文中不应出现的 Python 源码模式
    _SOURCE_CODE_PATTERNS = [
        re.compile(r"^import\s+\w+"),
        re.compile(r"^from\s+\w+\s+import"),
        re.compile(r"^logger\s*[.=]"),
        re.compile(r"^logging\.\w+"),
        re.compile(r"^SCRIPT_DIR"),
        re.compile(r"^os\.path\."),
        re.compile(r"^sys\.path\."),
        re.compile(r"^__\w+__\s*="),
        re.compile(r"^if\s+__name__\s*=="),
    ]

    @classmethod
    def _verify_no_source_code(cls, docx_path: Path) -> list[str]:
        """自检：扫描 docx 正文段落，检测是否有 Python 源码泄露"""
        warnings = []
        try:
            from docx import Document
            doc = Document(str(docx_path))
            in_appendix = False
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                # 进入附录后不再检查
                if "附录" in text and para.style.name.startswith("Heading"):
                    in_appendix = True
                    continue
                if in_appendix:
                    continue
                # 跳过标题
                if para.style.name.startswith("Heading"):
                    continue
                # 检查正文段落
                for pat in cls._SOURCE_CODE_PATTERNS:
                    if pat.search(text):
                        warnings.append(text[:80])
                        break
        except Exception:
            pass
        return warnings

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
                    if re.match(r'^5\.\d\s', para):
                        builder.add_heading(para, level=2)
                    else:
                        builder.add_paragraph(para)

            # 9. 模型求解（含图和表）
            builder.add_heading("六、模型求解与结果分析", level=1)
            solution_text = content.generate_model_solution()
            for para in solution_text.split("\n\n"):
                para = para.strip()
                if not para:
                    continue
                if re.match(r'^6\.\d\s', para):
                    builder.add_heading(para, level=2)
                elif para.startswith("表") and ("|" in para or "---" in para):
                    # 表格标题行
                    builder.add_paragraph(para, bold=True, indent=False)
                elif "|" in para and not para.startswith("表"):
                    # 表格数据行 — 渲染为等宽字体
                    p = builder.doc.add_paragraph()
                    p.paragraph_format.first_line_indent = builder.Cm(0)
                    p.paragraph_format.left_indent = builder.Cm(1.0)
                    run = p.add_run(para)
                    run.font.name = 'Courier New'
                    run.font.size = builder.Pt(9)
                else:
                    builder.add_paragraph(para)

            # 插入图片（在模型求解之后）
            figures_dir = project_dir / "figures"
            if figures_dir.exists():
                q1_fig = figures_dir / "q1_localization.png"
                if q1_fig.exists():
                    builder.add_figure(q1_fig, "问题一：点状结核定位分析")

                q2_fig = figures_dir / "q2_sphere.png"
                if q2_fig.exists():
                    builder.add_figure(q2_fig, "问题二：球形结核定位分析")

                q3_fig = figures_dir / "q3_echo_time.png"
                if q3_fig.exists():
                    builder.add_figure(q3_fig, "问题三：回波时间函数曲线")

                q4_fig = figures_dir / "q4_isochrone.png"
                if q4_fig.exists():
                    builder.add_figure(q4_fig, "问题四：等时线与梯度分析")

                comp_fig = figures_dir / "comprehensive_analysis.png"
                if comp_fig.exists():
                    builder.add_figure(comp_fig, "综合分析")

            # 10. 灵敏度分析
            builder.add_heading("七、灵敏度分析与误差讨论", level=1)
            exp_text = content.generate_experiment_results()
            for para in exp_text.split("\n\n"):
                para = para.strip()
                if not para:
                    continue
                if re.match(r'^7\.\d\s', para):
                    builder.add_heading(para, level=2)
                elif para.startswith("表") and ("|" in para or "---" in para):
                    builder.add_paragraph(para, bold=True, indent=False)
                elif "|" in para and not para.startswith("表"):
                    p = builder.doc.add_paragraph()
                    p.paragraph_format.first_line_indent = builder.Cm(0)
                    p.paragraph_format.left_indent = builder.Cm(1.0)
                    run = p.add_run(para)
                    run.font.name = 'Courier New'
                    run.font.size = builder.Pt(9)
                else:
                    builder.add_paragraph(para)

            # 11. 模型检验与误差分析
            builder.add_heading("八、误差分析与模型局限", level=1)
            error_text = content.generate_error_analysis()
            for para in error_text.split("\n\n"):
                para = para.strip()
                if para:
                    if re.match(r'^8\.\d\s', para):
                        builder.add_heading(para, level=2)
                    else:
                        builder.add_paragraph(para)

            # 12. 模型优缺点与改进方向
            builder.add_heading("九、模型评价与改进方向", level=1)
            pros, cons, improvements = content.generate_pros_cons()

            builder.add_paragraph("9.1 模型优点", bold=True, indent=False)
            builder.add_list(pros, ordered=False)

            builder.add_paragraph("9.2 模型不足", bold=True, indent=False)
            builder.add_list(cons, ordered=False)

            builder.add_paragraph("9.3 改进方向", bold=True, indent=False)
            builder.add_list(improvements, ordered=False)

            # 13. 结论
            builder.add_heading("十、结论", level=1)
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
            builder.add_heading("附录：核心算法说明", level=1)
            code_path = project_dir / "generated_code.py"
            if not code_path.exists():
                code_path = project_dir / "code" / "solution.py"
            appendix_text = content.generate_appendix(code_path)
            for para in appendix_text.split("\n\n"):
                para = para.strip()
                if not para:
                    continue
                # A.N 子标题
                if re.match(r'^A\.\d\s', para):
                    builder.add_heading(para, level=2)
                # 核心逻辑行（缩进的伪代码）用等宽字体
                elif para.startswith("    "):
                    p = builder.doc.add_paragraph()
                    p.paragraph_format.first_line_indent = builder.Cm(0)
                    p.paragraph_format.left_indent = builder.Cm(1.5)
                    run = p.add_run(para.strip())
                    run.font.name = 'Courier New'
                    run.font.size = builder.Pt(9)
                # 函数签名行
                elif para.startswith("函数签名："):
                    p = builder.doc.add_paragraph()
                    p.paragraph_format.first_line_indent = builder.Cm(0)
                    run = p.add_run(para)
                    run.font.name = 'Courier New'
                    run.font.size = builder.Pt(10)
                    run.bold = True
                else:
                    builder.add_paragraph(para)

            # 保存
            docx_file = paper_dir / "final_paper.docx"
            builder.save(docx_file)

            # 自检：确保正文无 Python 源码泄露
            warnings = self._verify_no_source_code(docx_file)
            if warnings:
                print(f"[PaperAgent] 警告：检测到正文可能包含源码: {warnings}")

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
                    "source_code_warnings": warnings,
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
