"""
核心编排器
管理 Agent 的顺序执行流程 (DAG)
提供详细进度报告和执行摘要
"""

import time
from pathlib import Path
from typing import Optional

from .config import AppConfig, load_config
from .core.llm_client import LLMClient
from .core.project_manager import ProjectManager
from .agents import (
    AgentContext,
    ParserAgent,
    StrategyAgent,
    CodeAgent,
    ExperimentAgent,
    PaperAgent,
    GitHubAgent,
)


# Agent 中文名称映射
AGENT_LABELS = {
    "parser": "题目解析",
    "strategy": "建模策略",
    "code": "代码执行",
    "experiment": "实验分析",
    "paper": "论文写作",
    "github": "GitHub自动化",
}


class Orchestrator:
    """
    编排器
    按照 DAG 顺序执行各 Agent，输出进度和摘要
    """

    def __init__(self, config: AppConfig | None = None):
        self.config = config or load_config()
        self.llm = LLMClient(self.config.llm)
        self.project_manager = ProjectManager(self.config.project.projects_dir)

        self.agents = {
            "parser": ParserAgent(self.config, self.llm),
            "strategy": StrategyAgent(self.config, self.llm),
            "code": CodeAgent(self.config, self.llm),
            "experiment": ExperimentAgent(self.config, self.llm),
            "paper": PaperAgent(self.config, self.llm),
            "github": GitHubAgent(self.config, self.llm),
        }

        self.pipeline = [
            "parser",
            "strategy",
            "code",
            "experiment",
            "paper",
            "github",
        ]

    def execute(
        self,
        problem_file: str | Path,
        project_name: str = "mathmodel",
    ) -> dict:
        """
        执行完整的建模流程

        Returns:
            包含 success, project_dir, results, summary, timing 的字典
        """
        problem_file = Path(problem_file)
        if not problem_file.exists():
            raise FileNotFoundError(f"题目文件不存在: {problem_file}")

        # 创建项目工作区
        project_dir = self.project_manager.create_project(project_name)

        # 初始化上下文
        context = AgentContext(
            project_dir=project_dir,
            problem_file=problem_file,
        )

        # 执行 Pipeline
        results = {}
        timing = {}
        total_start = time.time()
        n_agents = len(self.pipeline)

        for idx, agent_name in enumerate(self.pipeline):
            agent = self.agents[agent_name]
            label = AGENT_LABELS.get(agent_name, agent_name)
            progress = f"[{idx + 1}/{n_agents}]"

            print(f"\n{progress} 执行 {label} Agent ({agent.name})...")
            step_start = time.time()

            try:
                result = agent.run(context)
                elapsed = time.time() - step_start
                timing[agent_name] = round(elapsed, 2)

                if result.success:
                    print(f"  [OK] {label} 完成 ({elapsed:.1f}s)")
                    self._update_context(context, agent_name, result.output)
                    self.project_manager.update_state(
                        project_dir,
                        status=f"{agent_name}_completed",
                        current_agent=agent_name,
                    )
                else:
                    print(f"  [FAIL] {label} 失败: {result.error}")
                    self.project_manager.update_state(
                        project_dir,
                        status="failed",
                        current_agent=agent_name,
                    )
                    results[agent_name] = result
                    break

                results[agent_name] = result

            except Exception as e:
                elapsed = time.time() - step_start
                timing[agent_name] = round(elapsed, 2)
                print(f"  [ERROR] {label} 异常: {e}")
                results[agent_name] = type("Result", (), {
                    "success": False,
                    "error": str(e),
                })()
                break

        total_elapsed = time.time() - total_start
        timing["total"] = round(total_elapsed, 2)

        # 最终状态
        all_success = all(r.success for r in results.values())
        self.project_manager.update_state(
            project_dir,
            status="completed" if all_success else "failed",
        )

        # 生成摘要
        summary = self._build_summary(results, timing, all_success, project_dir)

        return {
            "project_dir": str(project_dir),
            "success": all_success,
            "results": results,
            "summary": summary,
            "timing": timing,
        }

    def _build_summary(self, results: dict, timing: dict, success: bool, project_dir: Path) -> dict:
        """构建执行摘要"""
        completed = []
        failed = []
        for name in self.pipeline:
            if name in results:
                if results[name].success:
                    completed.append(AGENT_LABELS.get(name, name))
                else:
                    failed.append(AGENT_LABELS.get(name, name))

        # 收集输出文件
        output_files = {}
        if "paper" in results and results["paper"].success:
            meta = results["paper"].metadata or {}
            output_files["paper_md"] = meta.get("md_file")
            output_files["paper_docx"] = meta.get("docx_file")
        if "experiment" in results and results["experiment"].success:
            output_files["report"] = results["experiment"].output.get("report_file")
            output_files["plots"] = results["experiment"].output.get("plots", [])
        if "github" in results and results["github"].success:
            output_files["readme"] = results["github"].output.get("readme_file")
            output_files["summary_json"] = results["github"].output.get("summary_file")

        return {
            "status": "success" if success else "failed",
            "completed_agents": completed,
            "failed_agents": failed,
            "timing": timing,
            "output_files": output_files,
            "project_dir": str(project_dir),
        }

    def _update_context(self, context: AgentContext, agent_name: str, output):
        """根据 Agent 输出更新上下文"""
        if agent_name == "parser":
            context.problem_spec = output
        elif agent_name == "strategy":
            context.model_plan = output
        elif agent_name == "code":
            context.execution_result = output
        elif agent_name == "experiment":
            context.experiment_result = output
        elif agent_name == "paper":
            context.paper_draft = output

        context.history.append({
            "agent": agent_name,
            "output_type": type(output).__name__,
        })
