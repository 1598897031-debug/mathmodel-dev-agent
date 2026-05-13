"""
文件操作工具
提供安全的文件读写功能
"""

from pathlib import Path


def read_file(file_path: str | Path, encoding: str = "utf-8") -> str:
    """
    读取文件内容

    Args:
        file_path: 文件路径
        encoding: 编码格式

    Returns:
        文件内容字符串
    """
    with open(file_path, "r", encoding=encoding) as f:
        return f.read()


def write_file(
    file_path: str | Path,
    content: str,
    encoding: str = "utf-8",
) -> Path:
    """
    写入文件内容

    Args:
        file_path: 文件路径
        content: 要写入的内容
        encoding: 编码格式

    Returns:
        写入的文件路径
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        f.write(content)
    return path
