"""
ExperimentAgent 单元测试
"""

import math
from pathlib import Path

from mathmodel.config import AppConfig
from mathmodel.core.llm_client import LLMClient
from mathmodel.core.document_parser import ProblemSpec
from mathmodel.agents.experiment_agent import (
    ExperimentAgent,
    rmse,
    mape,
    accuracy,
    mae,
    r_squared,
    parse_stdout_results,
)
from mathmodel.agents.base import AgentContext


class TestMetrics:
    """指标计算测试"""

    def test_rmse_perfect(self):
        """完美预测的 RMSE"""
        assert rmse([1, 2, 3], [1, 2, 3]) == 0.0

    def test_rmse_with_error(self):
        """有误差的 RMSE"""
        result = rmse([1, 2, 3], [1.1, 2.1, 3.1])
        assert abs(result - 0.1) < 1e-10

    def test_rmse_empty(self):
        """空数据的 RMSE"""
        assert rmse([], []) == 0.0

    def test_mape_perfect(self):
        """完美预测的 MAPE"""
        assert mape([100, 200], [100, 200]) == 0.0

    def test_mape_with_error(self):
        """有误差的 MAPE"""
        result = mape([100, 200], [110, 220])
        assert abs(result - 10.0) < 1e-10

    def test_mape_with_zero(self):
        """包含零值的 MAPE"""
        result = mape([0, 100], [10, 100])
        assert result >= 0

    def test_accuracy_perfect(self):
        """完美预测的准确率"""
        assert accuracy([1, 2, 3], [1, 2, 3], threshold=0.1) == 100.0

    def test_accuracy_with_error(self):
        """有误差的准确率"""
        result = accuracy([100, 200], [105, 215], threshold=0.1)
        assert result == 100.0  # Both within 10%

    def test_mae_perfect(self):
        """完美预测的 MAE"""
        assert mae([1, 2, 3], [1, 2, 3]) == 0.0

    def test_mae_with_error(self):
        """有误差的 MAE"""
        result = mae([1, 2, 3], [2, 3, 4])
        assert result == 1.0

    def test_r_squared_perfect(self):
        """完美预测的 R^2"""
        assert r_squared([1, 2, 3], [1, 2, 3]) == 1.0

    def test_r_squared_empty(self):
        """空数据的 R^2"""
        assert r_squared([], []) == 0.0


class TestParseStdout:
    """stdout 解析测试"""

    def test_parse_numbers(self):
        """解析数值"""
        stdout = "RMSE=5.62\nMAPE=1.58\nR^2=0.998"
        parsed = parse_stdout_results(stdout)
        assert "rmse" in parsed["metrics"]
        assert parsed["metrics"]["rmse"] == 5.62

    def test_parse_json(self):
        """解析 JSON"""
        stdout = '{"result": 42}'
        parsed = parse_stdout_results(stdout)
        assert "parsed_json" in parsed

    def test_parse_empty(self):
        """空输出"""
        parsed = parse_stdout_results("")
        assert len(parsed["raw_numbers"]) == 0


class TestExperimentAgent:
    """ExperimentAgent 测试类"""

    def setup_method(self):
        """测试前准备"""
        self.config = AppConfig()
        self.llm = LLMClient(self.config.llm)
        self.agent = ExperimentAgent(self.config, self.llm)

    def test_agent_name(self):
        """测试 Agent 名称"""
        assert self.agent.name == "experiment"

    def test_run_without_result(self):
        """测试无执行结果时的处理"""
        context = AgentContext(project_dir=Path("."))
        result = self.agent.run(context)
        assert not result.success
        assert "缺少代码执行结果" in result.error

    def test_run_with_result(self):
        """测试有执行结果时的处理"""
        tmp_dir = Path("test_exp_output")
        tmp_dir.mkdir(exist_ok=True)
        try:
            exec_result = {
                "code": "test",
                "stdout": "RMSE=5.0\nMAPE=2.0",
                "stderr": "",
                "fix_history": [],
                "attempts": 1,
            }
            spec = ProblemSpec(title="Test", problem_type="prediction", objective="predict")
            plan = {"best_approach": "Linear Regression", "problem_type": "prediction"}
            context = AgentContext(
                project_dir=tmp_dir,
                execution_result=exec_result,
                problem_spec=spec,
                model_plan=plan,
            )
            result = self.agent.run(context)
            assert result.success
            assert "metrics" in result.output
            assert "report" in result.output
            assert result.output["report_file"].endswith("experiment_report.md")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_generate_report(self):
        """测试报告生成"""
        metrics = {"rmse": 5.0, "mape": 2.0, "r_squared": 0.95}
        plots = [Path("test.png")]
        spec = ProblemSpec(title="Test", problem_type="prediction")
        plan = {"best_approach": "LR"}
        context = AgentContext(
            project_dir=Path("."),
            problem_spec=spec,
            model_plan=plan,
        )
        report = self.agent._generate_report(context, metrics, plots, "test output")
        assert "Experiment Report" in report
        assert "RMSE" in report
        assert "test output" in report

    def test_calculate_metrics(self):
        """测试指标计算"""
        actual = [100, 200, 300, 400, 500]
        predicted = [102, 198, 305, 395, 510]
        metrics = self.agent._calculate_metrics(actual, predicted)
        assert "rmse" in metrics
        assert "mape" in metrics
        assert "r_squared" in metrics
        assert metrics["n_samples"] == 5

    def test_calculate_metrics_empty(self):
        """测试空数据指标计算"""
        metrics = self.agent._calculate_metrics([], [])
        assert "error" in metrics

    def test_calculate_metrics_with_zeros(self):
        """测试包含零值的指标计算"""
        actual = [0, 100, 200]
        predicted = [10, 110, 210]
        metrics = self.agent._calculate_metrics(actual, predicted)
        assert "rmse" in metrics
        assert metrics["rmse"] >= 0
