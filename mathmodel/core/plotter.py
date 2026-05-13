"""
绘图封装模块
封装 matplotlib，提供常用的数学建模绘图功能
"""

from pathlib import Path
from typing import Optional


class Plotter:
    """
    绘图工具类
    提供数学建模常用的图表绘制功能
    """

    def __init__(self, output_dir: str | Path = "."):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def line_chart(
        self,
        x_data: list,
        y_data: list,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        filename: str = "line_chart.png",
    ) -> Path:
        """
        绘制折线图

        Args:
            x_data: X 轴数据
            y_data: Y 轴数据
            title: 图表标题
            x_label: X 轴标签
            y_label: Y 轴标签
            filename: 输出文件名

        Returns:
            生成的图片路径
        """
        try:
            import matplotlib
            matplotlib.use("Agg")  # 非交互式后端
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("请安装 matplotlib: pip install matplotlib")

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(x_data, y_data, marker="o")
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(True, alpha=0.3)

        output_path = self.output_dir / filename
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return output_path

    def bar_chart(
        self,
        categories: list[str],
        values: list[float],
        title: str = "",
        filename: str = "bar_chart.png",
    ) -> Path:
        """绘制柱状图"""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("请安装 matplotlib: pip install matplotlib")

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(categories, values)
        ax.set_title(title)
        ax.set_ylabel("数值")

        output_path = self.output_dir / filename
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return output_path
