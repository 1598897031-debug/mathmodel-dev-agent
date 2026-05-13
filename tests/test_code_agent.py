"""
CodeAgent 单元测试
"""

from pathlib import Path

from mathmodel.config import AppConfig
from mathmodel.core.llm_client import LLMClient
from mathmodel.core.code_executor import CodeExecutor
from mathmodel.core.document_parser import ProblemSpec
from mathmodel.agents.code_agent import CodeAgent, CODE_TEMPLATES
from mathmodel.agents.base import AgentContext


class TestCodeAgent:
    """CodeAgent 测试类"""

    def setup_method(self):
        """测试前准备"""
        self.config = AppConfig()
        self.llm = LLMClient(self.config.llm)
        self.agent = CodeAgent(self.config, self.llm)

    def test_agent_name(self):
        """测试 Agent 名称"""
        assert self.agent.name == "code"

    def test_run_without_plan(self):
        """测试无 ModelPlan 时的处理"""
        context = AgentContext(project_dir=Path("."))
        result = self.agent.run(context)
        assert not result.success
        assert "缺少建模方案" in result.error

    def test_run_with_plan(self):
        """测试有 ModelPlan 时的处理"""
        tmp_dir = Path("test_code_output")
        tmp_dir.mkdir(exist_ok=True)
        try:
            plan = {
                "problem_type": "优化类",
                "best_approach": "线性规划",
                "approaches": [{"name": "线性规划", "principle": "test"}],
            }
            context = AgentContext(project_dir=tmp_dir, model_plan=plan)
            result = self.agent.run(context)
            assert result.success
            assert "code" in result.output
            assert result.output["stdout"] != ""
            assert result.output["attempts"] >= 1
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_template_optimization(self):
        """测试优化类模板代码可运行"""
        code = CODE_TEMPLATES["优化类"]
        result = self.agent.executor.run(code)
        assert result.success, f"Optimization template failed: {result.stderr}"
        assert "最大利润" in result.stdout or "profit" in result.stdout.lower()

    def test_template_prediction(self):
        """测试预测类模板代码可运行"""
        code = CODE_TEMPLATES["预测类"]
        result = self.agent.executor.run(code)
        assert result.success, f"Prediction template failed: {result.stderr}"
        assert "线性回归" in result.stdout or "linear" in result.stdout.lower()

    def test_template_path_planning(self):
        """测试路径规划类模板代码可运行"""
        code = CODE_TEMPLATES["路径规划类"]
        result = self.agent.executor.run(code)
        assert result.success, f"Path planning template failed: {result.stderr}"
        assert "最短路径" in result.stdout or "shortest" in result.stdout.lower()

    def test_template_statistics(self):
        """测试统计类模板代码可运行"""
        code = CODE_TEMPLATES["统计类"]
        result = self.agent.executor.run(code)
        assert result.success, f"Statistics template failed: {result.stderr}"
        assert "t检验" in result.stdout or "t_test" in result.stdout.lower()

    def test_template_covers_all_types(self):
        """测试模板覆盖所有问题类型"""
        for ptype in ["优化类", "预测类", "路径规划类", "统计类"]:
            assert ptype in CODE_TEMPLATES, f"Missing template for {ptype}"

    def test_extract_code_from_markdown(self):
        """测试从 markdown 代码块提取代码"""
        text = 'Some text\n```python\nprint("hello")\n```\nMore text'
        code = self.agent._extract_code(text)
        assert 'print("hello")' in code

    def test_extract_code_bare(self):
        """测试提取裸代码"""
        text = '```print("hello")```'
        code = self.agent._extract_code(text)
        assert "hello" in code

    def test_build_log(self):
        """测试日志构建"""
        from mathmodel.core.code_executor import ExecResult
        exec_result = ExecResult(success=True, stdout="test output", stderr="", return_code=0)
        fix_history = [{"attempt": 1, "error": "test error", "status": "fixed"}]
        log = self.agent._build_log("code", exec_result, fix_history, 1)
        assert "成功" in log
        assert "test output" in log
        assert "test error" in log

    def test_generate_from_template_optimization(self):
        """测试从模板生成优化类代码"""
        plan = {"problem_type": "优化类", "best_approach": "LP"}
        spec = ProblemSpec(title="test")
        code = self.agent._generate_from_template(plan, spec)
        assert "linprog" in code or "solve" in code

    def test_generate_from_template_prediction(self):
        """测试从模板生成预测类代码"""
        plan = {"problem_type": "预测类", "best_approach": "回归"}
        spec = ProblemSpec(title="test")
        code = self.agent._generate_from_template(plan, spec)
        assert "slope" in code or "predict" in code.lower()

    def test_code_saves_to_project_dir(self):
        """测试代码保存到项目目录"""
        tmp_dir = Path("test_code_save")
        tmp_dir.mkdir(exist_ok=True)
        try:
            plan = {"problem_type": "路径规划类", "best_approach": "Dijkstra", "approaches": []}
            context = AgentContext(project_dir=tmp_dir, model_plan=plan)
            self.agent.run(context)
            assert (tmp_dir / "code" / "solution.py").exists()
            assert (tmp_dir / "code" / "execution_log.txt").exists()
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
