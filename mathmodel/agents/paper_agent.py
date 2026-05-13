"""
论文写作 Agent (Paper Writer Agent)
根据实验结果自动生成数学建模论文
支持 Markdown 输出和 Word 导出
"""

import json
import re
from pathlib import Path
from datetime import datetime

from ..core.llm_client import LLMClient, Message
from ..core.document_parser import ProblemSpec
from ..config import AppConfig
from .base import BaseAgent, AgentContext, AgentResult

# ==================== LLM Prompt ====================

PAPER_SYSTEM_PROMPT = """\
你是一个数学建模论文写作专家。根据给定的题目信息、建模方案和实验结果，生成完整的数学建模论文。

要求：
1. 语言正式、逻辑清晰
2. 数学公式使用 LaTeX 格式 (如 $E=mc^2$)
3. 图表引用规范 (如 [图1])
4. 结构完整，包含摘要、问题重述、模型假设等所有章节
5. 内容详实，每个章节至少 200 字

输出格式：Markdown 格式论文"""

# ==================== Word 导出 ====================

def markdown_to_docx(markdown_text: str, output_path: Path) -> bool:
    """
    将 Markdown 转换为 Word 文档

    Args:
        markdown_text: Markdown 文本
        output_path: 输出文件路径

    Returns:
        是否成功
    """
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        return False

    doc = Document()

    # 设置默认字体
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(12)

    lines = markdown_text.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 跳过空行
        if not line:
            i += 1
            continue

        # 标题
        if line.startswith('# ') and not line.startswith('## '):
            heading = doc.add_heading(line[2:].strip(), level=0)
            heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif line.startswith('## '):
            doc.add_heading(line[3:].strip(), level=1)
        elif line.startswith('### '):
            doc.add_heading(line[4:].strip(), level=2)
        elif line.startswith('#### '):
            doc.add_heading(line[5:].strip(), level=3)
        # 表格
        elif line.startswith('|') and '|' in line[1:]:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i].strip())
                i += 1
            i -= 1  # 回退一行，因为外层循环会 i += 1

            if len(table_lines) >= 2:
                # 解析表头
                headers = [c.strip() for c in table_lines[0].split('|')[1:-1]]
                # 跳过分隔线
                data_rows = []
                for row_line in table_lines[2:]:
                    row = [c.strip() for c in row_line.split('|')[1:-1]]
                    data_rows.append(row)

                if headers:
                    table = doc.add_table(rows=1 + len(data_rows), cols=len(headers))
                    table.style = 'Table Grid'
                    # 表头
                    for j, h in enumerate(headers):
                        cell = table.rows[0].cells[j]
                        cell.text = h
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                run.bold = True
                    # 数据行
                    for r_idx, row in enumerate(data_rows):
                        for c_idx, val in enumerate(row):
                            if c_idx < len(headers):
                                table.rows[r_idx + 1].cells[c_idx].text = val
                    doc.add_paragraph()  # 表格后空行
        # 列表
        elif line.startswith('- ') or line.startswith('* '):
            doc.add_paragraph(line[2:].strip(), style='List Bullet')
        elif re.match(r'^\d+\.\s', line):
            text = re.sub(r'^\d+\.\s', '', line)
            doc.add_paragraph(text.strip(), style='List Number')
        # 引用块
        elif line.startswith('> '):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.5)
            run = p.add_run(line[2:].strip())
            run.italic = True
        # 水平线
        elif line.startswith('---') or line.startswith('***'):
            doc.add_paragraph('_' * 50)
        # 普通段落
        else:
            # 处理加粗和斜体
            p = doc.add_paragraph()
            # 简单处理：去掉 markdown 格式符号
            clean_text = line
            clean_text = re.sub(r'\*\*(.+?)\*\*', r'\1', clean_text)
            clean_text = re.sub(r'\*(.+?)\*', r'\1', clean_text)
            clean_text = re.sub(r'\$(.+?)\$', r'\1', clean_text)
            p.add_run(clean_text)

        i += 1

    try:
        doc.save(str(output_path))
        return True
    except Exception:
        return False


# ==================== Agent 实现 ====================


class PaperAgent(BaseAgent):
    """
    论文写作 Agent
    输入: 全部中间产物 (ProblemSpec, ModelPlan, 执行结果, 实验结果)
    输出: 论文 Markdown + Word 文档
    """

    name = "paper"

    def run(self, context: AgentContext) -> AgentResult:
        """
        执行论文生成

        流程:
        1. 收集所有前序 Agent 的输出
        2. 生成论文 Markdown
        3. 保存 Markdown 文件
        4. 导出 Word 文档
        """
        try:
            project_dir = context.project_dir
            paper_dir = project_dir / "paper"
            paper_dir.mkdir(parents=True, exist_ok=True)

            # 1. 生成论文 Markdown
            paper = self._generate_paper(context)

            # 2. 保存 Markdown
            md_file = paper_dir / "paper.md"
            md_file.write_text(paper, encoding="utf-8")

            # 3. 导出 Word
            docx_file = paper_dir / "paper.docx"
            docx_success = markdown_to_docx(paper, docx_file)

            return AgentResult(
                success=True,
                agent_name=self.name,
                output=paper,
                metadata={
                    "md_file": str(md_file),
                    "docx_file": str(docx_file) if docx_success else None,
                    "docx_success": docx_success,
                },
            )

        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                error=str(e),
            )

    def _generate_paper(self, context: AgentContext) -> str:
        """生成论文 Markdown"""
        spec = context.problem_spec
        plan = context.model_plan
        exec_result = context.execution_result
        exp_result = context.experiment_result

        # 有 API key 时调用 LLM 生成
        if self.config.llm.claude_api_key or self.config.llm.openai_api_key:
            return self._generate_with_llm(context)

        # 无 API key 时使用模板
        return self._generate_from_template(spec, plan, exec_result, exp_result)

    def _generate_with_llm(self, context: AgentContext) -> str:
        """调用 LLM 生成论文"""
        spec = context.problem_spec
        plan = context.model_plan
        exec_result = context.execution_result
        exp_result = context.experiment_result

        user_content = f"""请根据以下信息生成数学建模论文：

## 题目信息
- 标题: {spec.title if spec else '未知'}
- 问题类型: {spec.problem_type if spec else '未知'}
- 描述: {(spec.description[:800] if spec else '未知')}
- 目标: {spec.objective if spec else '未知'}
- 变量: {', '.join(spec.variables) if spec and spec.variables else '待确定'}
- 约束: {', '.join(spec.constraints) if spec and spec.constraints else '待确定'}

## 建模方案
- 推荐方案: {plan.get('best_approach', '未知') if plan else '未知'}
- 方案原理: {self._get_approach_principle(plan)}

## 执行结果
- 代码输出: {(exec_result.get('stdout', '')[:500] if exec_result else '无')}

## 实验指标
- 指标: {json.dumps(exp_result.get('metrics', {}), ensure_ascii=False) if exp_result else '无'}

请生成完整的论文，包含摘要、问题重述、问题分析、模型假设、符号说明、模型建立与求解、模型检验、模型评价与推广、参考文献。"""

        messages = [
            Message(role="system", content=PAPER_SYSTEM_PROMPT),
            Message(role="user", content=user_content),
        ]

        return self.llm.chat(messages, temperature=0.3)

    def _generate_from_template(self, spec, plan, exec_result, exp_result) -> str:
        """从模板生成论文"""
        title = spec.title if spec else "数学建模问题"
        problem_type = spec.problem_type if spec else "未知"
        objective = spec.objective if spec else "未知"
        description = spec.description if spec else "未知"
        best_approach = plan.get("best_approach", "未知") if plan else "未知"
        approach_principle = self._get_approach_principle(plan)

        # 提取实验指标
        metrics = {}
        if exp_result:
            metrics = exp_result.get("metrics", {})

        # 生成摘要
        abstract = self._generate_abstract(spec, plan, metrics)

        # 生成各章节
        paper = f"""# {title}

## 摘要

{abstract}

---

## 一、问题重述

### 1.1 题目背景

{description[:500] if len(description) > 500 else description}

### 1.2 问题要求

"""
        # 添加求解要求
        if spec and spec.requirements:
            for i, req in enumerate(spec.requirements, 1):
                paper += f"{i}. {req}\n"
        else:
            paper += "1. 建立数学模型\n2. 求解最优方案\n3. 分析结果\n"

        paper += f"""
---

## 二、问题分析

本题属于**{problem_type}**问题。

"""
        if spec and spec.variables:
            paper += "### 2.1 变量分析\n\n"
            for var in spec.variables:
                paper += f"- {var}\n"
            paper += "\n"

        if spec and spec.constraints:
            paper += "### 2.2 约束分析\n\n"
            for c in spec.constraints:
                paper += f"- {c}\n"
            paper += "\n"

        paper += f"""### 2.3 目标分析

本题的目标是：{objective}

---

## 三、模型假设

"""
        assumptions = self._generate_assumptions(spec)
        for i, assumption in enumerate(assumptions, 1):
            paper += f"{i}. {assumption}\n"

        paper += f"""
---

## 四、符号说明

"""
        if spec and spec.variables:
            paper += "| 符号 | 含义 |\n|------|------|\n"
            for var in spec.variables:
                parts = var.split(" - ", 1)
                symbol = parts[0].strip()
                meaning = parts[1].strip() if len(parts) > 1 else "待说明"
                paper += f"| {symbol} | {meaning} |\n"
        else:
            paper += "| 符号 | 含义 |\n|------|------|\n| x | 决策变量 |\n| c | 目标函数系数 |\n"

        paper += f"""
---

## 五、模型建立与求解

### 5.1 模型选择

根据问题分析，本题采用 **{best_approach}** 方法进行求解。

### 5.2 模型原理

{approach_principle if approach_principle else '该方法通过数学优化技术，在满足约束条件下寻找最优解。'}

### 5.3 模型求解

"""
        # 添加执行结果
        if exec_result and exec_result.get("stdout"):
            paper += "```text\n"
            paper += exec_result["stdout"][:1000]
            paper += "\n```\n"
        else:
            paper += "代码执行结果待补充。\n"

        paper += f"""
---

## 六、模型检验

"""
        if metrics:
            paper += "### 6.1 评估指标\n\n"
            paper += "| 指标 | 值 | 说明 |\n|------|-----|------|\n"
            for key, value in metrics.items():
                desc = {
                    "rmse": "均方根误差，越小越好",
                    "mape": "平均绝对百分比误差 (%)",
                    "mae": "平均绝对误差",
                    "r_squared": "决定系数，越接近1越好",
                    "accuracy_10pct": "10%误差范围内准确率 (%)",
                    "accuracy_20pct": "20%误差范围内准确率 (%)",
                    "n_samples": "样本数量",
                }.get(key, "")
                paper += f"| {key} | {value} | {desc} |\n"

            # 性能评价
            r2 = metrics.get("r_squared", 0)
            if isinstance(r2, (int, float)):
                if r2 > 0.9:
                    paper += "\n**结论**: 模型拟合效果优秀 (R² > 0.9)\n"
                elif r2 > 0.7:
                    paper += "\n**结论**: 模型拟合效果良好 (0.7 < R² < 0.9)\n"
                elif r2 > 0.5:
                    paper += "\n**结论**: 模型拟合效果一般 (0.5 < R² < 0.7)\n"
                else:
                    paper += "\n**结论**: 模型拟合效果较差 (R² < 0.5)，建议改进模型\n"
        else:
            paper += "模型检验结果待补充。\n"

        paper += f"""
---

## 七、模型评价与推广

### 7.1 模型优点

"""
        pros = self._generate_model_pros(plan)
        for p in pros:
            paper += f"- {p}\n"

        paper += """
### 7.2 模型缺点

"""
        cons = self._generate_model_cons(plan)
        for c in cons:
            paper += f"- {c}\n"

        paper += """
### 7.3 改进方向

"""
        improvements = self._generate_improvements(plan)
        for imp in improvements:
            paper += f"- {imp}\n"

        paper += """
### 7.4 推广应用

本模型具有良好的可扩展性，可推广到类似问题的求解中。

---

## 参考文献

"""
        refs = self._generate_references()
        for i, ref in enumerate(refs, 1):
            paper += f"[{i}] {ref}\n"

        paper += f"""
---

*本文由 MathModel Dev Agent 自动生成*
*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

        return paper

    def _generate_abstract(self, spec, plan, metrics) -> str:
        """生成摘要"""
        title = spec.title if spec else "数学建模问题"
        problem_type = spec.problem_type if spec else "未知"
        best_approach = plan.get("best_approach", "未知") if plan else "未知"

        abstract = f"""本文针对"{title}"问题，采用{best_approach}方法进行了研究。

"""

        if spec and spec.description:
            abstract += f"首先，对问题进行了详细分析，明确了问题类型为{problem_type}。"
            abstract += "其次，建立了数学模型，"
            if spec.objective:
                abstract += f"以{spec.objective}为目标，"
            abstract += "在满足约束条件下寻求最优解。\n\n"

        abstract += f"实验结果表明，所建立的模型能够有效求解该问题。"

        r2 = metrics.get("r_squared", None)
        if r2 is not None:
            if isinstance(r2, (int, float)):
                if r2 > 0.9:
                    abstract += f"模型拟合效果优秀，R² = {r2:.4f}。"
                elif r2 > 0.7:
                    abstract += f"模型拟合效果良好，R² = {r2:.4f}。"
                else:
                    abstract += f"模型拟合效果一般，R² = {r2:.4f}，存在改进空间。"

        abstract += "\n\n**关键词**: 数学建模; " + (problem_type if problem_type else "优化问题") + "; " + best_approach

        return abstract

    def _generate_assumptions(self, spec) -> list:
        """生成模型假设"""
        assumptions = [
            "数据真实可靠，能够反映实际情况",
            "问题中的参数在研究期间保持稳定",
            "忽略次要因素的影响，聚焦主要变量",
        ]

        if spec:
            if "优化" in (spec.problem_type or ""):
                assumptions.append("目标函数和约束条件能够准确描述实际问题")
                assumptions.append("所有决策变量均为连续或离散可处理")
            elif "预测" in (spec.problem_type or ""):
                assumptions.append("历史数据具有代表性，能够反映未来趋势")
                assumptions.append("影响因素在预测期内不发生剧烈变化")
            elif "路径" in (spec.problem_type or ""):
                assumptions.append("网络结构稳定，边权已知")
                assumptions.append("起点和终点固定")

        return assumptions

    def _generate_model_pros(self, plan) -> list:
        """生成模型优点"""
        pros = [
            "模型结构清晰，易于理解和实现",
            "求解效率高，能够在合理时间内得到结果",
        ]

        if plan:
            approaches = plan.get("approaches", [])
            if approaches:
                best = approaches[0]
                pros.extend(best.get("pros", [])[:2])

        return pros

    def _generate_model_cons(self, plan) -> list:
        """生成模型缺点"""
        cons = [
            "模型对参数变化较为敏感",
            "假设条件可能与实际情况存在偏差",
        ]

        if plan:
            approaches = plan.get("approaches", [])
            if approaches:
                best = approaches[0]
                cons.extend(best.get("cons", [])[:1])

        return cons

    def _generate_improvements(self, plan) -> list:
        """生成改进方向"""
        return [
            "可引入更多变量提高模型精度",
            "可采用多种方法对比验证",
            "可进行灵敏度分析评估参数影响",
        ]

    def _generate_references(self) -> list:
        """生成参考文献"""
        return [
            "姜启源, 谢金星, 叶俊. 数学模型(第五版). 高等教育出版社, 2018.",
            "司守奎, 孙兆亮. 数学建模算法与应用(第2版). 国防工业出版社, 2015.",
            "Sheldon M. Ross. Introduction to Probability Models. Academic Press, 2019.",
        ]

    def _get_approach_principle(self, plan) -> str:
        """获取推荐方案的原理"""
        if not plan:
            return ""
        approaches = plan.get("approaches", [])
        if approaches:
            return approaches[0].get("principle", "")
        return ""
