"""
Orchestrator 单元测试
"""

import pytest
from pathlib import Path

from mathmodel.config import AppConfig
from mathmodel.orchestrator import Orchestrator


class TestOrchestrator:
    """Orchestrator 测试类"""

    def setup_method(self):
        """测试前准备"""
        self.config = AppConfig()
        self.orchestrator = Orchestrator(self.config)

    def test_init(self):
        """测试初始化"""
        assert self.orchestrator.config is not None
        assert self.orchestrator.llm is not None
        assert len(self.orchestrator.agents) == 6

    def test_pipeline_order(self):
        """测试执行顺序"""
        expected = ["parser", "strategy", "code", "experiment", "paper", "github"]
        assert self.orchestrator.pipeline == expected

    def test_execute_with_nonexistent_file(self):
        """测试不存在的文件"""
        with pytest.raises(FileNotFoundError):
            self.orchestrator.execute("nonexistent.txt")
