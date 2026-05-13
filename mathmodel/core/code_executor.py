"""
Python 代码安全执行沙箱
通过子进程执行代码，支持超时和资源限制
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from dataclasses import dataclass, field

from ..config import ExecutorConfig


@dataclass
class ExecResult:
    """执行结果"""
    success: bool = False              # 是否执行成功
    stdout: str = ""                   # 标准输出
    stderr: str = ""                   # 标准错误
    return_code: int = -1              # 返回码
    generated_files: list[str] = field(default_factory=list)  # 生成的文件


class CodeExecutor:
    """
    Python 代码执行器
    通过子进程隔离执行，支持超时控制
    """

    def __init__(self, config: ExecutorConfig | None = None):
        self.config = config or ExecutorConfig()

    def run(self, code: str, working_dir: str | Path | None = None) -> ExecResult:
        """
        执行 Python 代码

        Args:
            code: Python 源代码
            working_dir: 工作目录 (可选)

        Returns:
            ExecResult 执行结果
        """
        # 创建临时文件存放代码
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_file = Path(f.name)

        try:
            result = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=str(working_dir) if working_dir else None,
            )
            return ExecResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(
                success=False,
                stderr=f"执行超时 (超过 {self.config.timeout} 秒)",
                return_code=-1,
            )
        except Exception as e:
            return ExecResult(
                success=False,
                stderr=f"执行异常: {str(e)}",
                return_code=-1,
            )
        finally:
            temp_file.unlink(missing_ok=True)

    def run_file(self, file_path: str | Path) -> ExecResult:
        """
        执行 Python 文件

        Args:
            file_path: Python 文件路径

        Returns:
            ExecResult 执行结果
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return ExecResult(
                success=False,
                stderr=f"文件不存在: {file_path}",
            )

        try:
            result = subprocess.run(
                [sys.executable, str(file_path)],
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=str(file_path.parent),
            )
            return ExecResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(
                success=False,
                stderr=f"执行超时 (超过 {self.config.timeout} 秒)",
            )
