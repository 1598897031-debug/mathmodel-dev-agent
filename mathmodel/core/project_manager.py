"""
项目工作区管理
负责创建和管理每个建模项目的工作目录
"""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class ProjectState:
    """项目状态"""
    name: str = ""
    created_at: str = ""
    status: str = "initialized"  # initialized / parsing / modeling / executing / completed / failed
    current_agent: str = ""
    problem_file: str = ""
    intermediate_results: dict = field(default_factory=dict)


class ProjectManager:
    """
    项目管理器
    管理每个建模项目的工作目录和状态
    """

    def __init__(self, projects_dir: str | Path):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str) -> Path:
        """
        创建新项目

        Args:
            name: 项目名称

        Returns:
            项目目录路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_name = f"{name}_{timestamp}"
        project_dir = self.projects_dir / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (project_dir / "code").mkdir(exist_ok=True)
        (project_dir / "output").mkdir(exist_ok=True)
        (project_dir / "plots").mkdir(exist_ok=True)
        (project_dir / "paper").mkdir(exist_ok=True)

        # 初始化项目状态
        state = ProjectState(
            name=project_name,
            created_at=datetime.now().isoformat(),
        )
        self._save_state(project_dir, state)

        return project_dir

    def get_state(self, project_dir: str | Path) -> ProjectState:
        """获取项目状态"""
        state_file = Path(project_dir) / "project_state.json"
        if state_file.exists():
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ProjectState(**data)
        return ProjectState()

    def update_state(self, project_dir: str | Path, **kwargs):
        """更新项目状态"""
        state = self.get_state(project_dir)
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
        self._save_state(project_dir, state)

    def _save_state(self, project_dir: Path, state: ProjectState):
        """保存项目状态到文件"""
        state_file = project_dir / "project_state.json"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, ensure_ascii=False, indent=2)

    def list_projects(self) -> list[Path]:
        """列出所有项目"""
        return [
            d for d in self.projects_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
