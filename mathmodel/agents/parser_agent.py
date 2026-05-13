"""
问题解析 Agent (Problem Parser Agent)
负责从 TXT/Markdown/PDF 文件中提取数学建模题目信息
通过 LLM 进行结构化信息提取
"""

import json
import re
from pathlib import Path

from ..core.llm_client import LLMClient, Message
from ..core.document_parser import DocumentParser, ProblemSpec
from ..config import AppConfig
from .base import BaseAgent, AgentContext, AgentResult

# Parser Agent 的 System Prompt
PARSER_SYSTEM_PROMPT = """\
你是一个专业的数学建模题目解析专家。你的任务是从给定的题目文本中提取结构化的数学建模信息。

请严格按照以下 JSON 格式输出，不要添加任何额外解释：

{
  "title": "题目标题（从文本中提取或总结）",
  "description": "问题描述（简要概括题目背景和目标）",
  "variables": ["变量1名称 - 变量说明", "变量2名称 - 变量说明"],
  "constraints": ["约束条件1的完整描述", "约束条件2的完整描述"],
  "objective": "目标函数描述（最大化/最小化什么）",
  "problem_type": "从以下选项中选择一个: 预测类/优化类/路径规划类/统计类/其他",
  "given_data": ["已知数据1的描述", "已知数据2的描述"],
  "requirements": ["求解要求1", "求解要求2"]
}

分类标准：
- 预测类: 时间序列预测、回归分析、趋势预测、插值外推
- 优化类: 线性规划、非线性规划、整数规划、多目标优化、资源分配
- 路径规划类: 最短路径、旅行商问题(TSP)、车辆路径问题(VRP)、网络流
- 统计类: 假设检验、方差分析、回归分析、相关性分析、聚类分析
- 其他: 不属于以上类别的数学建模问题

输出格式要求：
1. 只输出 JSON，不要输出其他内容
2. JSON 必须是合法的格式
3. 字符串中不要使用换行符
4. 如果某个字段没有对应信息，使用空字符串或空列表"""


class ParserAgent(BaseAgent):
    """
    问题解析 Agent
    输入: 数学建模题目文件 (TXT/Markdown/PDF)
    输出: ProblemSpec 结构化题目信息
    """

    name = "parser"

    def __init__(self, config: AppConfig, llm: LLMClient):
        super().__init__(config, llm)
        self.doc_parser = DocumentParser()

    def run(self, context: AgentContext) -> AgentResult:
        """
        执行题目解析

        流程:
        1. 解析文档提取原始文本
        2. 调用 LLM 进行结构化提取
        3. 解析 JSON 响应为 ProblemSpec
        4. 如果 LLM 不可用，返回基础 ProblemSpec
        """
        try:
            if not context.problem_file:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    error="未指定题目文件",
                )

            # 1. 解析文档获取原始文本
            raw_spec = self.doc_parser.parse(context.problem_file)
            raw_text = raw_spec.description

            if not raw_text.strip():
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    error="文件内容为空",
                )

            # 2. 尝试调用 LLM 结构化提取
            spec = self._extract_with_llm(raw_text, raw_spec.title)

            return AgentResult(
                success=True,
                agent_name=self.name,
                output=spec,
                metadata={"file": str(context.problem_file)},
            )

        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                error=str(e),
            )

    def _extract_with_llm(self, raw_text: str, fallback_title: str) -> ProblemSpec:
        """
        调用 LLM 进行结构化提取
        如果 LLM 不可用，返回基础 ProblemSpec
        """
        # 检查是否有 API key
        if not self.config.llm.claude_api_key and not self.config.llm.openai_api_key:
            return ProblemSpec(
                title=fallback_title,
                description=raw_text,
                problem_type="待分类（无 API key）",
            )

        # 构建 prompt
        messages = self.build_prompt(raw_text)

        # 调用 LLM
        raw_response = self.llm.chat(messages, temperature=0.1)

        # 解析响应
        spec = self.parse_response(raw_response, fallback_title)
        spec.description = raw_text  # 保留原始文本
        return spec

    def build_prompt(self, raw_text: str) -> list[Message]:
        """
        构建 LLM prompt

        Args:
            raw_text: 题目原始文本

        Returns:
            消息列表
        """
        return [
            Message(role="system", content=PARSER_SYSTEM_PROMPT),
            Message(role="user", content=f"请解析以下数学建模题目：\n\n{raw_text}"),
        ]

    def parse_response(self, raw: str, fallback_title: str = "") -> ProblemSpec:
        """
        解析 LLM 响应为 ProblemSpec

        Args:
            raw: LLM 原始响应
            fallback_title: 备用标题

        Returns:
            ProblemSpec 对象
        """
        # 提取 JSON（可能包裹在 ```json ``` 代码块中）
        json_str = self._extract_json(raw)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # JSON 解析失败，返回基础 ProblemSpec
            return ProblemSpec(
                title=fallback_title,
                description=raw,
                problem_type="待分类（JSON 解析失败）",
            )

        # 转换为 ProblemSpec
        return ProblemSpec(
            title=data.get("title", fallback_title),
            description=data.get("description", ""),
            variables=data.get("variables", []),
            constraints=data.get("constraints", []),
            objective=data.get("objective", ""),
            problem_type=data.get("problem_type", "其他"),
            given_data=data.get("given_data", []),
            requirements=data.get("requirements", []),
        )

    def _extract_json(self, text: str) -> str:
        """
        从 LLM 响应中提取 JSON 字符串
        处理可能的 markdown 代码块包裹
        """
        # 尝试提取 ```json ... ``` 代码块
        pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 尝试提取 { ... } JSON 对象
        pattern = r"\{.*\}"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(0).strip()

        # 没有找到 JSON，返回原始文本
        return text.strip()
