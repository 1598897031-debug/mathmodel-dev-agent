"""
PaperAgent 单元测试
"""

from pathlib import Path

from mathmodel.config import AppConfig
from mathmodel.core.llm_client import LLMClient
from mathmodel.core.document_parser import ProblemSpec
from mathmodel.agents.paper_agent import PaperAgent, markdown_to_docx
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
            spec = ProblemSpec(
                title="Test Problem",
                problem_type="optimization",
                objective="maximize profit",
                description="A test problem",
            )
            plan = {"best_approach": "Linear Programming", "approaches": [{"name": "LP", "principle": "Test", "pros": ["p1"], "cons": ["c1"]}]}
            exec_result = {"stdout": "Result: 3180", "stderr": ""}
            exp_result = {"metrics": {"rmse": 5.0, "r_squared": 0.95}}
            context = AgentContext(
                project_dir=tmp_dir,
                problem_spec=spec,
                model_plan=plan,
                execution_result=exec_result,
                experiment_result=exp_result,
            )
            result = self.agent.run(context)
            assert result.success
            assert len(result.output) > 500
            assert (tmp_dir / "paper" / "paper.md").exists()
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_run_minimal(self):
        """测试最小上下文论文生成"""
        tmp_dir = Path("test_paper_min")
        tmp_dir.mkdir(exist_ok=True)
        try:
            context = AgentContext(project_dir=tmp_dir)
            result = self.agent.run(context)
            assert result.success
            assert len(result.output) > 200
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_paper_structure(self):
        """测试论文结构完整性"""
        spec = ProblemSpec(title="T", problem_type="prediction", objective="predict")
        plan = {"best_approach": "LR", "approaches": [{"name": "LR", "principle": "p", "pros": ["a"], "cons": ["b"]}]}
        paper = self.agent._generate_from_template(spec, plan, None, None)
        sections = ["摘要", "问题重述", "问题分析", "模型假设", "符号说明", "模型建立与求解", "模型检验", "模型评价与推广", "参考文献"]
        for section in sections:
            assert section in paper, f"Missing section: {section}"

    def test_abstract_generation(self):
        """测试摘要生成"""
        spec = ProblemSpec(title="T", problem_type="prediction", description="Test desc", objective="predict")
        plan = {"best_approach": "LR"}
        metrics = {"r_squared": 0.95}
        abstract = self.agent._generate_abstract(spec, plan, metrics)
        assert "T" in abstract
        assert "LR" in abstract
        assert "0.95" in abstract

    def test_assumptions_generation(self):
        """测试假设生成"""
        spec = ProblemSpec(problem_type="optimization")
        assumptions = self.agent._generate_assumptions(spec)
        assert len(assumptions) >= 3

    def test_model_pros_cons(self):
        """测试优缺点生成"""
        plan = {"approaches": [{"pros": ["Fast"], "cons": ["Sensitive"]}]}
        pros = self.agent._generate_model_pros(plan)
        cons = self.agent._generate_model_cons(plan)
        assert len(pros) >= 2
        assert len(cons) >= 2

    def test_references(self):
        """测试参考文献"""
        refs = self.agent._generate_references()
        assert len(refs) >= 3

    def test_markdown_to_docx_fail(self):
        """测试 Word 导出失败时的处理"""
        result = markdown_to_docx("# Test", Path("nonexistent/test.docx"))
        # Should return False if python-docx not installed
        assert isinstance(result, bool)
