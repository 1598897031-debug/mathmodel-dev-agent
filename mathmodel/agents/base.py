"""
Agent 基类
定义所有 Agent 的公共接口和数据结构
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..core.llm_client import LLMClient, Message
from ..core.document_parser import ProblemSpec
from ..config import AppConfig


@dataclass
class AgentContext:
    """
    Agent 执行上下文
    贯穿全流程的数据载体
    """
    project_dir: Path                                        # 项目工作区
    problem_file: Optional[Path] = None                      # 原始题目文件
    problem_spec: Optional[ProblemSpec] = None               # 解析后的题目
    model_plan: Optional[dict] = None                        # 建模方案
    execution_result: Optional[dict] = None                  # 代码执行结果
    experiment_result: Optional[dict] = None                 # 实验结果
    paper_draft: Optional[str] = None                        # 论文初稿
    history: list[dict] = field(default_factory=list)        # 前序 Agent 输出


@dataclass
class AgentResult:
    """
    Agent 执行结果
    每个 Agent 完成后返回的标准结果格式
    """
    success: bool = False
    agent_name: str = ""
    output: Any = None           # Agent 的主要输出
    error: Optional[str] = None  # 错误信息 (如果有)
    metadata: dict = field(default_factory=dict)  # 额外元数据


class BaseAgent(ABC):
    """
    Agent 抽象基类
    所有 Agent 必须继承此类并实现 run 方法
    """

    name: str = "base"

    def __init__(self, config: AppConfig, llm: LLMClient):
        self.config = config
        self.llm = llm

    @abstractmethod
    def run(self, context: AgentContext) -> AgentResult:
        """
        执行 Agent 任务

        Args:
            context: 执行上下文

        Returns:
            AgentResult 执行结果
        """
        pass

    def build_prompt(self, context: AgentContext) -> list[Message]:
        """
        构建 LLM prompt
        子类可覆盖以定制 prompt

        Args:
            context: 执行上下文

        Returns:
            消息列表
        """
        return [
            Message(role="system", content="你是一个数学建模专家。"),
            Message(role="user", content=str(context.problem_spec)),
        ]

    def parse_response(self, raw: str) -> Any:
        """
        解析 LLM 响应
        子类可覆盖以定制解析逻辑

        Args:
            raw: LLM 原始响应

        Returns:
            解析后的结构化数据
        """
        return raw
