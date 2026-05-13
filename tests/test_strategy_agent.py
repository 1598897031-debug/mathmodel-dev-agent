"""
StrategyAgent 单元测试
"""

import json
from pathlib import Path

from mathmodel.config import AppConfig
from mathmodel.core.llm_client import LLMClient
from mathmodel.core.document_parser import ProblemSpec
from mathmodel.agents.strategy_agent import StrategyAgent, KNOWLEDGE_BASE
from mathmodel.agents.base import AgentContext


class TestStrategyAgent:
    """StrategyAgent 测试类"""

    def setup_method(self):
        """测试前准备"""
        self.config = AppConfig()
        self.llm = LLMClient(self.config.llm)
        self.agent = StrategyAgent(self.config, self.llm)

    def test_agent_name(self):
        """测试 Agent 名称"""
        assert self.agent.name == "strategy"

    def test_run_without_spec(self):
        """测试无 ProblemSpec 时的处理"""
        context = AgentContext(project_dir=Path("."))
        result = self.agent.run(context)
        assert not result.success
        assert "缺少题目信息" in result.error

    def test_run_fallback_optimization(self):
        """测试 fallback - 优化类问题"""
        spec = ProblemSpec(
            title="生产调度优化",
            description="最大化利润",
            problem_type="优化类",
            objective="最大化总利润",
        )
        context = AgentContext(project_dir=Path("."), problem_spec=spec)
        result = self.agent.run(context)
        assert result.success
        plan = result.output
        assert plan["problem_type"] == "优化类"
        assert len(plan["approaches"]) >= 3
        assert plan["best_approach"] != ""
        assert plan["source"] == "fallback_knowledge_base"

    def test_run_fallback_prediction(self):
        """测试 fallback - 预测类问题"""
        spec = ProblemSpec(title="人口预测", problem_type="预测类")
        context = AgentContext(project_dir=Path("."), problem_spec=spec)
        result = self.agent.run(context)
        assert result.success
        assert result.output["problem_type"] == "预测类"
        assert len(result.output["approaches"]) >= 3

    def test_run_fallback_path_planning(self):
        """测试 fallback - 路径规划类问题"""
        spec = ProblemSpec(title="最短路径", problem_type="路径规划类")
        context = AgentContext(project_dir=Path("."), problem_spec=spec)
        result = self.agent.run(context)
        assert result.success
        assert result.output["problem_type"] == "路径规划类"
        assert len(result.output["approaches"]) >= 3

    def test_run_fallback_statistics(self):
        """测试 fallback - 统计类问题"""
        spec = ProblemSpec(title="假设检验", problem_type="统计类")
        context = AgentContext(project_dir=Path("."), problem_spec=spec)
        result = self.agent.run(context)
        assert result.success
        assert result.output["problem_type"] == "统计类"
        assert len(result.output["approaches"]) >= 3

    def test_approach_structure(self):
        """测试方案结构完整性"""
        spec = ProblemSpec(title="Test", problem_type="优化类")
        context = AgentContext(project_dir=Path("."), problem_spec=spec)
        result = self.agent.run(context)
        for approach in result.output["approaches"]:
            assert "name" in approach
            assert "principle" in approach
            assert "pros" in approach
            assert "cons" in approach
            assert "complexity" in approach
            assert "competition_suitability" in approach
            assert len(approach["pros"]) >= 2
            assert len(approach["cons"]) >= 1

    def test_knowledge_base_coverage(self):
        """测试知识库覆盖度"""
        for ptype in ["预测类", "优化类", "路径规划类", "统计类"]:
            assert ptype in KNOWLEDGE_BASE
            assert len(KNOWLEDGE_BASE[ptype]) >= 3

    def test_parse_response_valid(self):
        """测试有效 JSON 解析"""
        sample = json.dumps({
            "problem_type": "优化类",
            "problem_summary": "Test",
            "approaches": [{"name": "LP", "principle": "p", "pros": ["a"], "cons": ["b"], "complexity": "低", "competition_suitability": "高"}],
            "best_approach": "LP",
            "recommendation_reason": "reason",
        }, ensure_ascii=False)
        plan = self.agent.parse_response(sample)
        assert plan["best_approach"] == "LP"
        assert len(plan["approaches"]) == 1

    def test_parse_response_markdown_wrapped(self):
        """测试 markdown 代码块包裹的 JSON"""
        wrapped = '```json\n{"problem_type": "T", "approaches": [], "best_approach": "", "recommendation_reason": ""}\n```'
        plan = self.agent.parse_response(wrapped)
        assert "approaches" in plan

    def test_parse_response_invalid(self):
        """测试无效 JSON 的 fallback"""
        plan = self.agent.parse_response("not json")
        assert "approaches" in plan
        assert plan["best_approach"] == ""

    def test_to_markdown(self):
        """测试 Markdown 输出"""
        plan = {
            "problem_type": "优化类",
            "problem_summary": "Test",
            "approaches": [
                {"name": "LP", "principle": "原理", "pros": ["p1"], "cons": ["c1"],
                 "complexity": "低", "competition_suitability": "高", "required_tools": ["scipy"]},
            ],
            "best_approach": "LP",
            "recommendation_reason": "Best",
        }
        md = self.agent.to_markdown(plan)
        assert "# 建模方案推荐" in md
        assert "LP" in md
        assert "原理" in md

    def test_build_prompt(self):
        """测试 prompt 构建"""
        spec = ProblemSpec(title="T", problem_type="优化类", objective="max x")
        messages = self.agent.build_prompt(spec)
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert "T" in messages[1].content
        assert "优化类" in messages[1].content
