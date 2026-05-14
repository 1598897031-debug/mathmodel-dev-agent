"""
PaperAgent 单元测试
"""

import json
from pathlib import Path

from mathmodel.config import AppConfig
from mathmodel.core.llm_client import LLMClient
from mathmodel.core.document_parser import ProblemSpec
from mathmodel.agents.paper_agent import PaperAgent, PaperDocxBuilder, PaperContentGenerator
from mathmodel.agents.base import AgentContext


class TestPaperAgent:
    """PaperAgent 测试类"""

    def setup_method(self):
        """测试前准备"""
        self.config = AppConfig()
        self.llm = LLMClient(self.config.llm)
        self.agent = PaperAgent(self.config, self.llm)

    def test_agent_name(self):
        """测试 Agent 名称"""
        assert self.agent.name == "paper"

    def test_run_basic(self):
        """测试基本论文生成"""
        tmp_dir = Path("test_paper_output")
        tmp_dir.mkdir(exist_ok=True)
        try:
            # 准备必要的 JSON 文件
            problem_data = {
                "title": "测试问题",
                "source": "测试竞赛",
                "context": "这是一个测试问题",
                "questions": {
                    "Q1": {"title": "子问题一", "description": "测试描述"},
                },
            }
            results = {"Q1": {"nodule_A": {"x": 1.0, "y": 2.0, "z": 0.0}}}

            (tmp_dir / "parsed_problem.json").write_text(
                json.dumps(problem_data, ensure_ascii=False), encoding="utf-8"
            )
            (tmp_dir / "results.json").write_text(
                json.dumps(results, ensure_ascii=False), encoding="utf-8"
            )

            spec = ProblemSpec(
                title="测试问题",
                problem_type="optimization",
                objective="maximize profit",
                description="A test problem",
            )
            plan = {
                "best_approach": "Linear Programming",
                "approaches": [{"name": "LP", "principle": "Test"}],
            }
            context = AgentContext(
                project_dir=tmp_dir,
                problem_spec=spec,
                model_plan=plan,
                execution_result={"stdout": "Result: 3180"},
                experiment_result={"metrics": {"rmse": 5.0, "r_squared": 0.95}},
            )
            result = self.agent.run(context)
            assert result.success
            assert (tmp_dir / "paper" / "final_paper.docx").exists()
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_run_minimal(self):
        """测试最小上下文论文生成"""
        tmp_dir = Path("test_paper_min")
        tmp_dir.mkdir(exist_ok=True)
        try:
            # 准备必要的 JSON 文件
            problem_data = {"title": "Minimal", "context": "Minimal problem"}
            (tmp_dir / "parsed_problem.json").write_text(
                json.dumps(problem_data, ensure_ascii=False), encoding="utf-8"
            )
            (tmp_dir / "results.json").write_text("{}", encoding="utf-8")

            context = AgentContext(project_dir=tmp_dir)
            result = self.agent.run(context)
            assert result.success
            assert (tmp_dir / "paper" / "final_paper.docx").exists()
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_docx_structure(self):
        """测试 docx 结构完整性"""
        tmp_dir = Path("test_paper_struct")
        tmp_dir.mkdir(exist_ok=True)
        try:
            problem_data = {
                "title": "水下探测",
                "source": "竞赛A题",
                "context": "深海探测",
                "questions": {"Q1": {"title": "定位", "description": "求坐标"}},
            }
            results = {"Q1": {"nodule_A": {"x": 0, "y": 80, "z": 0}}}

            (tmp_dir / "parsed_problem.json").write_text(
                json.dumps(problem_data, ensure_ascii=False), encoding="utf-8"
            )
            (tmp_dir / "results.json").write_text(
                json.dumps(results, ensure_ascii=False), encoding="utf-8"
            )

            spec = ProblemSpec(title="水下探测", problem_type="定位")
            context = AgentContext(
                project_dir=tmp_dir,
                problem_spec=spec,
                model_plan={"best_approach": "几何定位"},
            )
            result = self.agent.run(context)
            assert result.success

            # 验证 docx 内容
            import sys
            sys.path.insert(0, "D:/Lib/site-packages")
            from docx import Document

            doc = Document(str(tmp_dir / "paper" / "final_paper.docx"))
            headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]

            required_sections = ["摘要", "问题重述", "问题分析", "模型假设", "符号说明",
                                 "模型建立", "模型求解", "结论", "参考文献"]
            for section in required_sections:
                found = any(section in h for h in headings)
                assert found, f"Missing section: {section}"
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
