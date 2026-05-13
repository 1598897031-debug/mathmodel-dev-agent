"""
配置管理模块
统一管理 API 密钥、模型选择、路径等配置项
"""

import os
from pathlib import Path
from dataclasses import dataclass, field

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class LLMConfig:
    """LLM 调用配置"""
    # Claude API
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 8192

    # OpenAI API (备用)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # 默认使用 Claude
    default_provider: str = "claude"


@dataclass
class ExecutorConfig:
    """代码执行配置"""
    timeout: int = 30           # 单次执行超时 (秒)
    max_retries: int = 3        # 最大重试次数
    max_memory_mb: int = 512    # 最大内存使用 (MB)


@dataclass
class ProjectConfig:
    """项目配置"""
    outputs_dir: Path = PROJECT_ROOT / "outputs"
    projects_dir: Path = PROJECT_ROOT / "projects"
    examples_dir: Path = PROJECT_ROOT / "examples"
    templates_dir: Path = PROJECT_ROOT / "mathmodel" / "templates"


@dataclass
class AppConfig:
    """应用总配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    executor: ExecutorConfig = field(default_factory=ExecutorConfig)
    project: ProjectConfig = field(default_factory=ProjectConfig)
    debug: bool = False
    verbose: bool = False


def load_config() -> AppConfig:
    """
    加载配置
    优先从环境变量读取，其次使用默认值
    """
    config = AppConfig()

    # 从环境变量加载 LLM 配置
    config.llm.claude_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    config.llm.openai_api_key = os.getenv("OPENAI_API_KEY", "")

    # 从环境变量加载调试选项
    config.debug = os.getenv("MATHMODEL_DEBUG", "").lower() == "true"
    config.verbose = os.getenv("MATHMODEL_VERBOSE", "").lower() == "true"

    return config
