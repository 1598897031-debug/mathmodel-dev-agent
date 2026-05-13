"""
ParserAgent 单元测试
"""

import json
from pathlib import Path

from mathmodel.config import AppConfig
from mathmodel.core.llm_client import LLMClient
from mathmodel.core.document_parser import ProblemSpec
from mathmodel.agents.parser_agent import ParserAgent
from mathmodel.agents.base import AgentContext


class TestParserAgent:
    """ParserAgent 测试类"""

    def setup_method(self):
        """测试前准备"""
        self.config = AppConfig()
        self.llm = LLMClient(self.config.llm)
        self.agent = ParserAgent(self.config, self.llm)

    def test_agent_name(self):
        """测试 Agent 名称"""
        assert self.agent.name == "parser"

    def test_run_without_file(self):
        """测试无文件时的处理"""
        context = AgentContext(project_dir=Path("."))
        result = self.agent.run(context)
        assert not result.success
        assert "未指定题目文件" in result.error

    def test_parse_txt_file(self):
        """测试 TXT 文件解析"""
        context = AgentContext(
            project_dir=Path("."),
            problem_file=Path("examples/sample_optimization.txt"),
        )
        result = self.agent.run(context)
        assert result.success
        assert result.output.title == "sample_optimization"
        assert len(result.output.description) > 0

    def test_parse_md_file(self):
        """测试 Markdown 文件解析"""
        # 创建临时 .md 文件
        md_file = Path("test_problem.md")
        md_file.write_text("# Test Problem\n\nThis is a test.", encoding="utf-8")
        try:
            context = AgentContext(
                project_dir=Path("."),
                problem_file=md_file,
            )
            result = self.agent.run(context)
            assert result.success
            assert result.output.title == "test_problem"
        finally:
            md_file.unlink()

    def test_parse_response_valid_json(self):
        """测试有效 JSON 响应解析"""
        sample = json.dumps({
            "title": "Test",
            "description": "Desc",
            "variables": ["x"],
            "constraints": ["c1"],
            "objective": "max x",
            "problem_type": "优化类",
            "given_data": [],
            "requirements": ["r1"],
        }, ensure_ascii=False)
        spec = self.agent.parse_response(sample, "fallback")
        assert spec.title == "Test"
        assert spec.problem_type == "优化类"
        assert spec.variables == ["x"]

    def test_parse_response_markdown_wrapped(self):
        """测试 markdown 代码块包裹的 JSON"""
        wrapped = '```json\n{"title": "T", "description": "D", "variables": [], "constraints": [], "objective": "", "problem_type": "其他", "given_data": [], "requirements": []}\n```'
        spec = self.agent.parse_response(wrapped, "fb")
        assert spec.title == "T"

    def test_parse_response_invalid_json(self):
        """测试无效 JSON 的 fallback"""
        spec = self.agent.parse_response("not json at all", "fallback")
        assert spec.title == "fallback"
        assert "待分类" in spec.problem_type

    def test_extract_json_from_markdown(self):
        """测试从 markdown 中提取 JSON"""
        text = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
        result = self.agent._extract_json(text)
        assert '{"key": "value"}' in result

    def test_extract_json_bare(self):
        """测试提取裸 JSON"""
        text = 'Here is the result: {"key": "value"} done.'
        result = self.agent._extract_json(text)
        assert '{"key": "value"}' in result
