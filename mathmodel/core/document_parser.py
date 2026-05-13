"""
文档解析器
支持 PDF 和 TXT 格式的数学建模题目解析
"""

from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ProblemSpec:
    """
    题目规格说明
    解析后的结构化题目信息
    """
    title: str = ""                         # 题目标题
    description: str = ""                   # 问题描述
    variables: list[str] = field(default_factory=list)     # 决策变量
    constraints: list[str] = field(default_factory=list)   # 约束条件
    objective: str = ""                     # 目标函数
    problem_type: str = ""                  # 问题类型 (预测/优化/路径规划/统计)
    given_data: list[str] = field(default_factory=list)    # 已知数据
    requirements: list[str] = field(default_factory=list)  # 求解要求


class DocumentParser:
    """
    文档解析器
    支持从 PDF 和 TXT 文件中提取数学建模题目信息
    """

    def parse(self, file_path: str | Path) -> ProblemSpec:
        """
        解析文档文件

        Args:
            file_path: 文件路径

        Returns:
            ProblemSpec 结构化题目信息
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix in (".txt", ".md", ".markdown"):
            return self._parse_text(file_path)
        elif suffix == ".pdf":
            return self._parse_pdf(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")

    def _parse_text(self, file_path: Path) -> ProblemSpec:
        """解析纯文本文件 (TXT/Markdown)"""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        spec = ProblemSpec()
        spec.description = content
        spec.title = file_path.stem
        return spec

    def _parse_pdf(self, file_path: Path) -> ProblemSpec:
        """
        解析 PDF 文件
        使用 PyPDF2 库提取文本
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("请安装 pypdf: pip install pypdf")

        reader = PdfReader(str(file_path))
        content = ""
        for page in reader.pages:
            content += page.extract_text() or ""

        spec = ProblemSpec()
        spec.description = content
        spec.title = file_path.stem
        return spec
