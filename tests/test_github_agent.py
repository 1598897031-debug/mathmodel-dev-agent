"""
GitHubAgent 单元测试
"""

import json
from pathlib import Path

from mathmodel.config import AppConfig
from mathmodel.core.llm_client import LLMClient
from mathmodel.core.document_parser import ProblemSpec
from mathmodel.agents.github_agent import GitHubAgent
from mathmodel.agents.base import AgentContext


class TestGitHubAgent:
    """GitHubAgent 测试类"""

    def setup_method(self):
        self.config = AppConfig()
        self.llm = LLMClient(self.config.llm)
        self.agent = GitHubAgent(self.config, self.llm)

    def test_agent_name(self):
        assert self.agent.name == "github"

    def test_run_basic(self):
        tmp_dir = Path("test_github_output")
        tmp_dir.mkdir(exist_ok=True)
        try:
            spec = ProblemSpec(
                title="Test Problem",
                problem_type="optimization",
                objective="maximize profit",
                description="A test problem for scheduling",
            )
            plan = {
                "best_approach": "Linear Programming",
                "approaches": [
                    {"name": "LP", "principle": "Linear optimization", "complexity": "low", "competition_suitability": "high", "recommended": True},
                    {"name": "ILP", "principle": "Integer programming", "complexity": "medium", "competition_suitability": "high", "recommended": False},
                ],
            }
            exp_result = {"metrics": {"rmse": 5.0, "r_squared": 0.95}}
            context = AgentContext(
                project_dir=tmp_dir,
                problem_spec=spec,
                model_plan=plan,
                experiment_result=exp_result,
            )
            result = self.agent.run(context)
            assert result.success
            assert result.output["readme_generated"]
            assert isinstance(result.output["committed"], bool)
            assert isinstance(result.output["pushed"], bool)
            assert (tmp_dir / "README.md").exists()
            assert (tmp_dir / "summary.json").exists()
            assert (tmp_dir / "PROJECT_DESCRIPTION.md").exists()
            assert (tmp_dir / "CHANGES.md").exists()
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_readme_generation(self):
        spec = ProblemSpec(
            title="生产调度问题",
            problem_type="优化类",
            objective="最小化成本",
        )
        plan = {
            "best_approach": "线性规划",
            "approaches": [{"name": "LP", "principle": "Principle", "complexity": "低", "competition_suitability": "高", "recommended": True}],
        }
        exp_result = {"metrics": {"rmse": 2.0, "r_squared": 0.98}}
        context = AgentContext(
            project_dir=Path("."),
            problem_spec=spec,
            model_plan=plan,
            experiment_result=exp_result,
        )
        readme = self.agent._generate_readme(context, spec, plan, exp_result)
        assert "生产调度问题" in readme
        assert "线性规划" in readme
        assert "rmse" in readme
        assert "2.0" in readme
        assert "PROJECT_DESCRIPTION.md" in readme
        assert "CHANGES.md" in readme

    def test_readme_minimal(self):
        context = AgentContext(project_dir=Path("."))
        readme = self.agent._generate_readme(context, None, None, None)
        assert "MathModel Dev Agent" in readme

    def test_project_description_generation(self):
        spec = ProblemSpec(
            title="生产调度问题",
            problem_type="优化类",
            objective="最小化成本",
            description="某工厂生产两种产品",
            variables=["x1 - 产品A产量", "x2 - 产品B产量"],
            constraints=["机器时间 <= 120", "人工时间 <= 90"],
        )
        plan = {
            "best_approach": "线性规划",
            "approaches": [
                {"name": "LP", "principle": "Linear optimization", "pros": ["高效"], "cons": ["仅限线性"], "complexity": "低", "competition_suitability": "高", "recommended": True},
            ],
        }
        desc = self.agent._generate_project_description(spec, plan)
        assert "生产调度问题" in desc
        assert "线性规划" in desc
        assert "x1 - 产品A产量" in desc
        assert "机器时间 <= 120" in desc
        assert "MathModel Dev Agent" in desc

    def test_project_description_minimal(self):
        desc = self.agent._generate_project_description(None, None)
        assert "MathModel Project" in desc
        assert "项目说明" in desc

    def test_version_log_generation(self):
        tmp_dir = Path("test_version_log")
        tmp_dir.mkdir(exist_ok=True)
        try:
            spec = ProblemSpec(title="Test", problem_type="optimization")
            log = self.agent._generate_version_log(tmp_dir, spec, commit_hash="abc1234def")
            assert "Changelog" in log
            assert "abc1234" in log
            assert "Test" in log

            # 写入文件再追加
            (tmp_dir / "CHANGES.md").write_text(log, encoding="utf-8")
            log2 = self.agent._generate_version_log(tmp_dir, spec, commit_hash="xyz789aaa")
            assert "abc1234" in log2  # 保留旧记录
            assert "xyz789a" in log2  # 包含新记录 (截断到7位)
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_version_log_no_commit_hash(self):
        tmp_dir = Path("test_vlog_nohash")
        tmp_dir.mkdir(exist_ok=True)
        try:
            spec = ProblemSpec(title="Test")
            log = self.agent._generate_version_log(tmp_dir, spec, commit_hash=None)
            assert "Changelog" in log
            assert "Test" in log
            assert "`" not in log  # 没有 commit hash 时不应有反引号
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_git_push_no_remote(self):
        tmp_dir = Path("test_push_noremote")
        tmp_dir.mkdir(exist_ok=True)
        try:
            from mathmodel.utils.git_ops import git_init
            git_init(tmp_dir)
            ok, msg = self.agent._try_git_push(tmp_dir)
            assert not ok
            assert "不存在" in msg or "not found" in msg.lower() or "origin" in msg.lower()
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_summary_generation(self):
        spec = ProblemSpec(
            title="Test",
            problem_type="prediction",
            objective="predict",
        )
        plan = {
            "best_approach": "LR",
            "approaches": [
                {"name": "LR", "complexity": "low", "recommended": True},
                {"name": "SVR", "complexity": "high", "recommended": False},
            ],
        }
        exp_result = {"metrics": {"rmse": 1.0, "mape": 3.0, "r_squared": 0.99}}
        context = AgentContext(
            project_dir=Path("test_summary_dir"),
            problem_spec=spec,
            model_plan=plan,
            experiment_result=exp_result,
        )
        summary = self.agent._generate_summary(context, spec, plan, exp_result)
        assert summary["project_name"] == "test_summary_dir"
        assert summary["problem"]["title"] == "Test"
        assert summary["solution"]["approach"] == "LR"
        assert len(summary["solution"]["approaches"]) == 2
        assert summary["metrics"]["rmse"] == 1.0
        assert summary["files"]["code"] == "code/solution.py"
        assert summary["files"]["description"] == "PROJECT_DESCRIPTION.md"
        assert summary["files"]["changelog"] == "CHANGES.md"

    def test_summary_minimal(self):
        context = AgentContext(project_dir=Path("."))
        summary = self.agent._generate_summary(context, None, None, None)
        assert isinstance(summary["project_name"], str)
        assert "generated_at" in summary
        assert summary["solution"]["approach"] == ""
        assert summary["metrics"] == {}

    def test_readme_includes_project_structure(self):
        context = AgentContext(project_dir=Path("my_project"))
        readme = self.agent._generate_readme(context, None, None, None)
        assert "PROJECT_DESCRIPTION.md" in readme
        assert "CHANGES.md" in readme
        assert "项目结构" in readme
