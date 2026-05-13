"""
Git 操作工具
封装常用的 git 命令: init, add, commit, push, log, remote
"""

import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: str | Path | None = None) -> tuple[bool, str]:
    """
    执行 git 命令

    Args:
        args: git 命令参数列表
        cwd: 工作目录

    Returns:
        (成功标志, 输出信息)
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return result.returncode == 0, result.stdout.strip() + "\n" + result.stderr.strip()
    except FileNotFoundError:
        return False, "git 未安装或不在 PATH 中"


def git_init(directory: str | Path) -> tuple[bool, str]:
    """初始化 git 仓库"""
    return _run_git(["init"], cwd=directory)


def git_add(directory: str | Path, files: list[str] | None = None) -> tuple[bool, str]:
    """
    添加文件到暂存区

    Args:
        directory: 仓库目录
        files: 文件列表 (None 表示添加所有)
    """
    if files:
        return _run_git(["add"] + files, cwd=directory)
    return _run_git(["add", "."], cwd=directory)


def git_commit(directory: str | Path, message: str) -> tuple[bool, str]:
    """提交更改"""
    return _run_git(["commit", "-m", message], cwd=directory)


def git_has_remote(directory: str | Path, name: str = "origin") -> bool:
    """检查指定 remote 是否存在"""
    ok, output = _run_git(["remote"], cwd=directory)
    if ok:
        return name in output.splitlines()
    return False


def git_remote_add(directory: str | Path, name: str, url: str) -> tuple[bool, str]:
    """
    添加 remote

    Args:
        directory: 仓库目录
        name: remote 名称 (如 origin)
        url: 远程仓库 URL
    """
    return _run_git(["remote", "add", name, url], cwd=directory)


def git_push(directory: str | Path, remote: str = "origin", branch: str = "main") -> tuple[bool, str]:
    """
    推送到远程仓库

    Args:
        directory: 仓库目录
        remote: remote 名称
        branch: 分支名
    """
    if not git_has_remote(directory, remote):
        return False, f"remote '{remote}' 不存在，跳过 push"
    return _run_git(["push", remote, branch], cwd=directory)


def git_current_branch(directory: str | Path) -> str:
    """获取当前分支名"""
    ok, output = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=directory)
    return output.strip() if ok else "main"


def git_log(directory: str | Path, n: int = 10) -> str:
    """
    获取最近 n 条 commit 日志 (纯文本格式)

    Args:
        directory: 仓库目录
        n: 返回条数

    Returns:
        日志文本
    """
    ok, output = _run_git(
        ["log", f"-{n}", "--oneline", "--date=short", "--format=%h %ad %s"],
        cwd=directory,
    )
    return output.strip() if ok else ""


def git_log_dict(directory: str | Path, n: int = 10) -> list[dict]:
    """
    获取最近 n 条 commit 日志 (结构化格式)

    Returns:
        [{"hash": "abc1234", "date": "2026-05-13", "message": "commit msg"}, ...]
    """
    ok, output = _run_git(
        ["log", f"-{n}", "--format=%h|%ad|%s", "--date=short"],
        cwd=directory,
    )
    if not ok or not output.strip():
        return []

    entries = []
    for line in output.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            entries.append({
                "hash": parts[0].strip(),
                "date": parts[1].strip(),
                "message": parts[2].strip(),
            })
    return entries
