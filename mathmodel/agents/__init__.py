"""
Agent 模块
包含所有六大 Agent 的实现
"""

from .base import BaseAgent, AgentContext, AgentResult
from .parser_agent import ParserAgent
from .strategy_agent import StrategyAgent
from .code_agent import CodeAgent
from .experiment_agent import ExperimentAgent
from .paper_agent import PaperAgent
from .github_agent import GitHubAgent

__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentResult",
    "ParserAgent",
    "StrategyAgent",
    "CodeAgent",
    "ExperimentAgent",
    "PaperAgent",
    "GitHubAgent",
]
