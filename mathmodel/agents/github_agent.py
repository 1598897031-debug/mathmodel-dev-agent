"""
GitHub 自动化 Agent (GitHub Automation Agent)
自动生成 README、项目说明、版本日志、git commit、git push
"""

import json
from pathlib import Path
from datetime import datetime

from ..core.llm_client import LLMClient, Message
from ..core.document_parser import ProblemSpec
from ..config import AppConfig
from ..utils.git_ops import (
    git_init,
    git_add,
    git_commit,
    git_push,
    git_log_dict,
    git_has_remote,
)
from .base import BaseAgent, AgentContext, AgentResult


class GitHubAgent(BaseAgent):
    """
    GitHub 自动化 Agent
    输入: 项目所有输出
    输出: README + PROJECT_DESCRIPTION + CHANGES + summary + git commit + push
    """

    name = "github"

    def run(self, context: AgentContext) -> AgentResult:
        """
        执行 GitHub 自动化

        流程:
        1. 生成 README.md
        2. 生成 PROJECT_DESCRIPTION.md
        3. 生成/追加 CHANGES.md (版本日志)
        4. 生成 summary.json
        5. git add + commit (获取 commit hash)
        6. git push (尝试，无 remote 则跳过)
        """
        try:
            project_dir = context.project_dir
            spec = context.problem_spec
            plan = context.model_plan
            exp_result = context.experiment_result

            # 1. 生成 README
            readme = self._generate_readme(context, spec, plan, exp_result)
            readme_file = project_dir / "README.md"
            readme_file.write_text(readme, encoding="utf-8")

            # 2. 生成项目说明
            desc = self._generate_project_description(spec, plan)
            desc_file = project_dir / "PROJECT_DESCRIPTION.md"
            desc_file.write_text(desc, encoding="utf-8")

            # 3. 生成版本日志
            version_log = self._generate_version_log(project_dir, spec, commit_hash=None)
            changes_file = project_dir / "CHANGES.md"
            changes_file.write_text(version_log, encoding="utf-8")

            # 4. 生成项目摘要
            summary = self._generate_summary(context, spec, plan, exp_result)
            summary_file = project_dir / "summary.json"
            summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

            # 5. git commit (返回 commit hash)
            commit_hash = self._try_git_commit(project_dir, spec)

            # 6. 更新版本日志 (写入 commit hash)
            if commit_hash:
                version_log = self._generate_version_log(project_dir, spec, commit_hash)
                changes_file.write_text(version_log, encoding="utf-8")

            # 7. git push (尝试)
            pushed, push_msg = self._try_git_push(project_dir)

            return AgentResult(
                success=True,
                agent_name=self.name,
                output={
                    "readme_generated": True,
                    "readme_file": str(readme_file),
                    "description_file": str(desc_file),
                    "version_log_file": str(changes_file),
                    "summary_file": str(summary_file),
                    "committed": commit_hash is not None,
                    "commit_hash": commit_hash,
                    "pushed": pushed,
                    "push_message": push_msg,
                },
            )

        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                error=str(e),
            )

    def _generate_readme(self, context, spec, plan, exp_result) -> str:
        """生成 README.md"""
        title = spec.title if spec else "MathModel Project"
        problem_type = spec.problem_type if spec else "未知"
        objective = spec.objective if spec else "未知"
        best_approach = plan.get("best_approach", "未知") if plan else "未知"

        metrics = {}
        if exp_result:
            metrics = exp_result.get("metrics", {})

        readme = f"""# {title}

MathModel Dev Agent 自动生成的数学建模项目。

## 项目信息

| 项目 | 内容 |
|------|------|
| 题目类型 | {problem_type} |
| 目标 | {objective} |
| 建模方法 | {best_approach} |
| 生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |

## 项目结构

```
{context.project_dir.name}/
├── code/                    # 求解代码
│   ├── solution.py          # 主求解代码
│   └── execution_log.txt    # 执行日志
├── plots/                   # 图表
├── paper/                   # 论文
│   ├── paper.md             # Markdown 论文
│   └── paper.docx           # Word 论文 (如有)
├── experiment_report.md     # 实验报告
├── PROJECT_DESCRIPTION.md   # 项目详细说明
├── CHANGES.md               # 版本变更日志
├── summary.json             # 项目摘要
└── README.md                # 本文件
```

## 求解方法

{best_approach}

"""
        if plan:
            approaches = plan.get("approaches", [])
            if approaches:
                readme += "### 候选方案\n\n"
                for i, a in enumerate(approaches[:3], 1):
                    flag = " **[推荐]**" if a.get("recommended") else ""
                    readme += f"{i}. **{a.get('name', '')}**{flag}\n"
                    readme += f"   - 原理: {a.get('principle', '')[:80]}...\n"
                    readme += f"   - 复杂度: {a.get('complexity', '')} | 比赛适用性: {a.get('competition_suitability', '')}\n"
                readme += "\n"

        if metrics:
            readme += "## 实验指标\n\n"
            readme += "| 指标 | 值 |\n|------|-----|\n"
            for key, value in metrics.items():
                readme += f"| {key} | {value} |\n"
            readme += "\n"

        readme += """## 使用方法

```bash
# 运行求解代码
python code/solution.py

# 查看论文
cat paper/paper.md
```

## 输出文件

- `code/solution.py` - 可运行的求解代码
- `paper/paper.md` - 数学建模论文
- `experiment_report.md` - 实验分析报告
- `PROJECT_DESCRIPTION.md` - 项目详细说明
- `CHANGES.md` - 版本变更日志
- `plots/` - 可视化图表

## 相关文档

- [项目说明](PROJECT_DESCRIPTION.md) - 详细的项目描述与背景
- [变更日志](CHANGES.md) - 版本历史记录

---

*Generated by MathModel Dev Agent*
"""

        return readme

    def _generate_project_description(self, spec, plan) -> str:
        """生成项目详细说明"""
        title = spec.title if spec else "MathModel Project"
        problem_type = spec.problem_type if spec else "未知"
        objective = spec.objective if spec else "未知"
        description = spec.description if spec else "暂无详细描述"
        best_approach = plan.get("best_approach", "未知") if plan else "未知"

        # 变量说明
        variables_section = ""
        if spec and spec.variables:
            variables_section = "\n### 变量列表\n\n"
            for var in spec.variables:
                variables_section += f"- {var}\n"

        # 约束说明
        constraints_section = ""
        if spec and spec.constraints:
            constraints_section = "\n### 约束条件\n\n"
            for c in spec.constraints:
                constraints_section += f"- {c}\n"

        # 需求说明
        requirements_section = ""
        if spec and spec.requirements:
            requirements_section = "\n### 求解要求\n\n"
            for i, req in enumerate(spec.requirements, 1):
                requirements_section += f"{i}. {req}\n"

        # 方案详情
        approaches_section = ""
        if plan and plan.get("approaches"):
            approaches_section = "\n## 候选建模方案\n\n"
            for i, a in enumerate(plan["approaches"][:5], 1):
                flag = " (推荐)" if a.get("recommended") else ""
                approaches_section += f"### {i}. {a.get('name', '')}{flag}\n\n"
                approaches_section += f"**原理**: {a.get('principle', '未知')}\n\n"
                pros = a.get("pros", [])
                cons = a.get("cons", [])
                if pros:
                    approaches_section += "**优点**:\n"
                    for p in pros:
                        approaches_section += f"- {p}\n"
                if cons:
                    approaches_section += "\n**缺点**:\n"
                    for c in cons:
                        approaches_section += f"- {c}\n"
                approaches_section += f"\n**复杂度**: {a.get('complexity', '未知')} | **比赛适用性**: {a.get('competition_suitability', '未知')}\n\n"

        return f"""# {title} - 项目说明

## 1. 问题背景

**题目类型**: {problem_type}

**求解目标**: {objective}

### 问题描述

{description[:2000]}

{variables_section}
{constraints_section}
{requirements_section}

## 2. 建模方法

采用 **{best_approach}** 方法进行求解。

{approaches_section}

## 3. 项目概述

本项目由 MathModel Dev Agent 自动生成，包含完整的数学建模流程：

1. **题目解析** - 自动提取问题类型、变量、约束
2. **建模策略** - 推荐最优建模方案
3. **代码生成** - 自动生成可运行的求解代码
4. **实验分析** - 计算评估指标、生成可视化图表
5. **论文写作** - 自动生成数学建模论文
6. **版本管理** - 自动 git commit 和 push

## 4. 文件说明

| 文件 | 说明 |
|------|------|
| `code/solution.py` | 主求解代码 |
| `paper/paper.md` | Markdown 格式论文 |
| `paper/paper.docx` | Word 格式论文 (如有) |
| `experiment_report.md` | 实验分析报告 |
| `plots/` | 可视化图表目录 |
| `summary.json` | 项目结构化摘要 |
| `CHANGES.md` | 版本变更日志 |

---

*Generated by MathModel Dev Agent - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    def _generate_version_log(self, project_dir: Path, spec, commit_hash: str | None = None) -> str:
        """
        生成/追加版本日志 CHANGES.md

        如果文件已存在则追加新条目，否则创建新文件。
        """
        title = spec.title if spec else "MathModel Project"
        changes_file = project_dir / "CHANGES.md"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        commit_info = f" (`{commit_hash[:7]}`)" if commit_hash else ""

        new_entry = f"""## [{now}]{commit_info} - {title}

### 变更内容

- 自动生成 README.md
- 自动生成 PROJECT_DESCRIPTION.md
- 自动生成项目摘要 summary.json
- 生成求解代码 code/solution.py
- 生成实验报告 experiment_report.md
- 生成数学建模论文 paper/paper.md

"""

        # 如果文件已存在，追加新条目
        if changes_file.exists():
            existing = changes_file.read_text(encoding="utf-8")
            # 在文件头之后插入新条目
            header_end = existing.find("\n\n")
            if header_end != -1:
                header = existing[:header_end + 2]
                body = existing[header_end + 2:]
                return header + new_entry + body
            return existing + "\n" + new_entry

        # 创建新文件
        return f"""# Changelog

本文件记录 MathModel Dev Agent 项目的版本变更历史。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

{new_entry}"""

    def _generate_summary(self, context, spec, plan, exp_result) -> dict:
        """生成项目摘要"""
        metrics = {}
        if exp_result:
            metrics = exp_result.get("metrics", {})

        approaches = []
        if plan:
            for a in plan.get("approaches", [])[:3]:
                approaches.append({
                    "name": a.get("name", ""),
                    "complexity": a.get("complexity", ""),
                    "recommended": a.get("recommended", False),
                })

        return {
            "project_name": context.project_dir.name,
            "generated_at": datetime.now().isoformat(),
            "problem": {
                "title": spec.title if spec else "",
                "type": spec.problem_type if spec else "",
                "objective": spec.objective if spec else "",
            },
            "solution": {
                "approach": plan.get("best_approach", "") if plan else "",
                "approaches": approaches,
            },
            "metrics": metrics,
            "files": {
                "code": "code/solution.py",
                "paper": "paper/paper.md",
                "report": "experiment_report.md",
                "readme": "README.md",
                "description": "PROJECT_DESCRIPTION.md",
                "changelog": "CHANGES.md",
            },
        }

    def _try_git_commit(self, project_dir: Path, spec) -> str | None:
        """
        尝试 git commit

        Returns:
            commit hash (成功时) 或 None (失败时)
        """
        try:
            # 检查是否在 git 仓库中
            from mathmodel.utils.git_ops import _run_git
            is_repo, _ = _run_git(["rev-parse", "--git-dir"], cwd=str(project_dir))

            if not is_repo:
                # 不是 git 仓库，初始化
                git_init(project_dir)
                git_add(project_dir)
                title = spec.title if spec else "MathModel Project"
                ok, _ = git_commit(project_dir, f"Initial commit: {title}")
            else:
                # 已是 git 仓库，添加并提交
                git_add(project_dir)
                title = spec.title if spec else "MathModel Project"
                ok, _ = git_commit(project_dir, f"Update: {title}")

            if ok:
                # 获取 commit hash
                log = git_log_dict(project_dir, n=1)
                if log:
                    return log[0]["hash"]
            return None

        except Exception:
            return None

    def _try_git_push(self, project_dir: Path) -> tuple[bool, str]:
        """
        尝试 git push

        Returns:
            (是否成功, 消息)
        """
        try:
            branch = "main"
            from mathmodel.utils.git_ops import git_current_branch
            branch = git_current_branch(project_dir)

            ok, msg = git_push(project_dir, remote="origin", branch=branch)
            return ok, msg

        except Exception as e:
            return False, str(e)
