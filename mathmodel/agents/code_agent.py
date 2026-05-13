"""
代码执行 Agent (Code Execution Agent)
根据建模方案自动生成 Python 求解代码，执行并自动 debug
支持: 时间序列预测、回归模型、优化模型
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field

from ..core.llm_client import LLMClient, Message
from ..core.code_executor import CodeExecutor, ExecResult
from ..core.document_parser import ProblemSpec
from ..config import AppConfig
from .base import BaseAgent, AgentContext, AgentResult

# ==================== System Prompt ====================

CODE_SYSTEM_PROMPT = """\
你是一个 Python 数学建模代码生成专家。根据建模方案生成完整可运行的 Python 求解代码。

要求：
1. 生成完整的、可直接运行的 Python 代码
2. 包含所有必要的 import 语句
3. 代码结构清晰，有 solve() 主函数
4. 结果打印到标准输出 (print)
5. 使用常见的科学计算库 (numpy, scipy, matplotlib, pandas, scikit-learn 等)
6. 代码中不要使用中文字符作为变量名
7. 在文件末尾调用 solve() 并打印结果

输出格式：
```python
# 完整的 Python 代码
```

只输出代码，不要输出其他解释文字。"""

FIX_SYSTEM_PROMPT = """\
你是一个 Python 代码调试专家。以下代码运行时出现了错误，请修复代码。

常见错误类型及修复策略：
- ImportError/ModuleNotFoundError: 添加缺失的 import 或在代码中检查
- SyntaxError/IndentationError: 修复语法错误
- TypeError: 检查函数参数类型，添加类型转换
- ValueError: 检查数组维度、NaN/Inf、边界条件
- FileNotFoundError: 使用 Path(__file__).parent 构建相对路径
- LinAlgError: 矩阵奇异时改用 np.linalg.lstsq 或 np.linalg.pinv
- ZeroDivisionError: 添加除零保护

要求：
1. 分析错误原因
2. 修复代码中的问题
3. 输出修复后的完整代码
4. 不要改变代码的核心逻辑，只修复错误
5. 如果是 ImportError，确保在代码开头检查并处理

输出格式：
```python
# 修复后的完整 Python 代码
```

只输出修复后的代码，不要输出其他解释。"""

# ==================== 代码模板 (Fallback) ====================

CODE_TEMPLATES = {
    "优化类": '''"""
MathModel Dev Agent - 优化模型求解代码 (纯标准库版本)
"""
import math

def solve():
    """线性规划求解 (单纯形法简化版)"""
    print("=" * 50)
    print("  优化模型求解")
    print("=" * 50)

    # 示例: max 50x + 40y
    # 约束: 2x + y <= 120, x + 3y <= 90, x >= 0, y >= 0
    # 使用穷举顶点法求解

    # 找到可行域顶点
    vertices = []

    # 约束交点
    # 2x + y = 120 与 x + 3y = 90 的交点
    # 解方程组: 2x + y = 120, x + 3y = 90
    # => x = (360 - 90) / 5 = 54, y = (120 - 108) / 5 = 12/5 = 2.4... 不对
    # 2x + y = 120 => y = 120 - 2x
    # x + 3(120 - 2x) = 90 => x + 360 - 6x = 90 => -5x = -270 => x = 54
    # y = 120 - 2*54 = 12
    # 但 x + 3y = 54 + 36 = 90 OK
    # 2x + y = 108 + 12 = 120 OK

    vertices.append((0, 0))           # 原点
    vertices.append((60, 0))          # 2x+y=120, y=0
    vertices.append((0, 30))          # x+3y=90, x=0
    vertices.append((54, 12))         # 两约束交点

    # 计算目标函数值
    best_val = -float("inf")
    best_point = (0, 0)
    print("\\n顶点分析:")
    for x, y in vertices:
        val = 50 * x + 40 * y
        feasible = (2 * x + y <= 120 + 0.001) and (x + 3 * y <= 90 + 0.001)
        status = "可行" if feasible else "不可行"
        print(f"  ({x}, {y}): 利润={val:.0f} [{status}]")
        if feasible and val > best_val:
            best_val = val
            best_point = (x, y)

    print(f"\\n最优解:")
    print(f"  产品A产量: {best_point[0]:.2f}")
    print(f"  产品B产量: {best_point[1]:.2f}")
    print(f"  最大利润: {best_val:.2f}")

    return {"x": list(best_point), "profit": best_val}

if __name__ == "__main__":
    solve()
''',

    "预测类": '''"""
MathModel Dev Agent - 预测模型求解代码 (纯标准库版本)
"""
def solve():
    """预测模型求解 - 最小二乘法"""
    print("=" * 50)
    print("  预测模型求解")
    print("=" * 50)

    # 示例数据: 年份 -> 人口(万)
    years = [2010, 2012, 2014, 2016, 2018, 2020]
    population = [500, 520, 545, 575, 610, 650]
    n = len(years)

    # 方法1: 线性回归 (最小二乘法)
    sum_x = sum(years)
    sum_y = sum(population)
    sum_xy = sum(x * y for x, y in zip(years, population))
    sum_x2 = sum(x * x for x in years)

    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
    intercept = (sum_y - slope * sum_x) / n

    # R^2
    y_mean = sum_y / n
    ss_tot = sum((y - y_mean) ** 2 for y in population)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(years, population))
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    pred_2025 = slope * 2025 + intercept
    pred_2030 = slope * 2030 + intercept

    print(f"\\n线性回归结果:")
    print(f"  斜率: {slope:.4f}")
    print(f"  截距: {intercept:.2f}")
    print(f"  R^2: {r_squared:.4f}")
    print(f"  2025年预测: {pred_2025:.2f} 万")
    print(f"  2030年预测: {pred_2030:.2f} 万")

    # 方法2: 指数拟合 (对数变换后线性回归)
    import math
    log_pop = [math.log(y) for y in population]
    sum_ly = sum(log_pop)
    sum_xly = sum(x * ly for x, ly in zip(years, log_pop))

    slope_exp = (n * sum_xly - sum_x * sum_ly) / (n * sum_x2 - sum_x * sum_x)
    intercept_exp = (sum_ly - slope_exp * sum_x) / n

    pred_exp_2025 = math.exp(slope_exp * 2025 + intercept_exp)
    pred_exp_2030 = math.exp(slope_exp * 2030 + intercept_exp)

    print(f"\\n指数拟合结果:")
    print(f"  2025年预测: {pred_exp_2025:.2f} 万")
    print(f"  2030年预测: {pred_exp_2030:.2f} 万")

    return {
        "linear": {"2025": pred_2025, "2030": pred_2030, "r_squared": r_squared},
        "exponential": {"2025": pred_exp_2025, "2030": pred_exp_2030},
    }

if __name__ == "__main__":
    solve()
''',

    "路径规划类": '''"""
MathModel Dev Agent - 路径规划模型求解代码 (纯标准库版本)
"""
import heapq

def solve():
    """Dijkstra最短路径求解"""
    print("=" * 50)
    print("  路径规划模型求解")
    print("=" * 50)

    # 示例图: 邻接表 {node: [(neighbor, weight), ...]}
    graph = {
        'A': [('B', 4), ('C', 2)],
        'B': [('A', 4), ('C', 1), ('D', 5)],
        'C': [('A', 2), ('B', 1), ('D', 8), ('E', 10)],
        'D': [('B', 5), ('C', 8), ('E', 2)],
        'E': [('C', 10), ('D', 2)],
    }

    start, end = 'A', 'E'

    # Dijkstra算法
    dist = {node: float('inf') for node in graph}
    dist[start] = 0
    prev = {node: None for node in graph}
    pq = [(0, start)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in graph[u]:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                prev[v] = u
                heapq.heappush(pq, (dist[v], v))

    # 回溯路径
    path = []
    node = end
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()

    print(f"\\n最短路径: {' -> '.join(path)}")
    print(f"最短距离: {dist[end]}")

    return {"path": path, "distance": dist[end]}

if __name__ == "__main__":
    solve()
''',

    "统计类": '''"""
MathModel Dev Agent - 统计分析模型求解代码 (纯标准库版本)
"""
import math

def solve():
    """统计分析求解"""
    print("=" * 50)
    print("  统计分析模型求解")
    print("=" * 50)

    # 示例数据: 三种教学方法的成绩
    method_a = [85, 78, 92, 88, 76, 95, 82, 90]
    method_b = [72, 68, 75, 80, 65, 70, 78, 73]
    method_c = [90, 95, 88, 92, 98, 85, 91, 87]

    def mean(data):
        return sum(data) / len(data)

    def std(data):
        m = mean(data)
        return math.sqrt(sum((x - m) ** 2 for x in data) / len(data))

    def t_test(a, b):
        n1, n2 = len(a), len(b)
        m1, m2 = mean(a), mean(b)
        v1 = sum((x - m1) ** 2 for x in a) / (n1 - 1)
        v2 = sum((x - m2) ** 2 for x in b) / (n2 - 1)
        se = math.sqrt(v1 / n1 + v2 / n2)
        t = (m1 - m2) / se if se > 0 else 0
        return t

    # 描述性统计
    print("\\n描述性统计:")
    for name, data in [("方法A", method_a), ("方法B", method_b), ("方法C", method_c)]:
        print(f"  {name}: 均值={mean(data):.2f}, 标准差={std(data):.2f}")

    # t检验 (A vs B)
    t_stat = t_test(method_a, method_b)
    print(f"\\nt检验 (方法A vs 方法B):")
    print(f"  t统计量: {t_stat:.4f}")
    # 简化判断: |t| > 2 通常显著
    sig = "差异显著" if abs(t_stat) > 2 else "差异不显著"
    print(f"  结论: {sig}")

    # 简化方差分析 (组间均方/组内均方)
    all_data = method_a + method_b + method_c
    grand_mean = mean(all_data)
    k = 3
    N = len(all_data)
    ss_between = sum(len(g) * (mean(g) - grand_mean) ** 2 for g in [method_a, method_b, method_c])
    ss_within = sum(sum((x - mean(g)) ** 2 for x in g) for g in [method_a, method_b, method_c])
    ms_between = ss_between / (k - 1)
    ms_within = ss_within / (N - k)
    f_stat = ms_between / ms_within if ms_within > 0 else 0

    print(f"\\n方差分析:")
    print(f"  F统计量: {f_stat:.4f}")
    sig_anova = "差异显著" if f_stat > 3.84 else "差异不显著"
    print(f"  结论: {sig_anova} (alpha=0.05, F临界值约3.84)")

    return {
        "t_test_ab": {"t_stat": t_stat},
        "anova": {"f_stat": f_stat},
    }

if __name__ == "__main__":
    solve()
''',
}


class CodeAgent(BaseAgent):
    """
    代码执行 Agent
    输入: ModelPlan (建模方案)
    输出: Python 代码 + 执行结果 + debug 日志
    """

    name = "code"

    def __init__(self, config: AppConfig, llm: LLMClient):
        super().__init__(config, llm)
        self.executor = CodeExecutor(config.executor)

    def run(self, context: AgentContext) -> AgentResult:
        """
        执行代码生成与运行

        流程:
        1. 根据建模方案生成 Python 代码
        2. 保存代码到项目目录
        3. 执行代码
        4. 如果失败，分析错误并修复，最多重试 3 次
        5. 保存运行日志和修复记录
        """
        try:
            if not context.model_plan:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    error="缺少建模方案 (ModelPlan)",
                )

            plan = context.model_plan
            project_dir = context.project_dir
            code_dir = project_dir / "code"
            code_dir.mkdir(parents=True, exist_ok=True)

            # 1. 生成代码
            code = self._generate_code(plan, context.problem_spec)

            # 保存初始代码
            code_file = code_dir / "solution.py"
            code_file.write_text(code, encoding="utf-8")

            # 2. 执行循环 (最多重试 max_retries 次)
            max_retries = self.config.executor.max_retries
            fix_history = []
            current_code = code

            for attempt in range(max_retries + 1):
                print(f"    [CodeAgent] Attempt {attempt + 1}/{max_retries + 1}")

                exec_result = self.executor.run(current_code, working_dir=code_dir)

                if exec_result.success:
                    # 执行成功
                    log = self._build_log(current_code, exec_result, fix_history, attempt)
                    log_file = code_dir / "execution_log.txt"
                    log_file.write_text(log, encoding="utf-8")

                    return AgentResult(
                        success=True,
                        agent_name=self.name,
                        output={
                            "code": current_code,
                            "stdout": exec_result.stdout,
                            "stderr": exec_result.stderr,
                            "fix_history": fix_history,
                            "attempts": attempt + 1,
                        },
                        metadata={"retries": attempt},
                    )

                # 执行失败，尝试修复
                if attempt < max_retries:
                    fix_record = {
                        "attempt": attempt + 1,
                        "error": exec_result.stderr,
                    }
                    print(f"    [CodeAgent] Error detected, attempting fix...")

                    fixed_code = self._fix_code(
                        current_code, exec_result.stderr, plan, context.problem_spec
                    )

                    if fixed_code:
                        current_code = fixed_code
                        fix_record["status"] = "fixed"
                        fix_record["lesson"] = self._extract_lesson(exec_result.stderr)
                        # 保存修复后的代码
                        fix_file = code_dir / f"solution_fix_{attempt + 1}.py"
                        fix_file.write_text(fixed_code, encoding="utf-8")
                    else:
                        fix_record["status"] = "fix_failed"

                    fix_history.append(fix_record)

            # 所有重试都失败
            log = self._build_log(current_code, exec_result, fix_history, max_retries)
            log_file = code_dir / "execution_log.txt"
            log_file.write_text(log, encoding="utf-8")

            return AgentResult(
                success=False,
                agent_name=self.name,
                error=f"代码执行失败，已重试 {max_retries} 次",
                output={
                    "code": current_code,
                    "stdout": exec_result.stdout,
                    "stderr": exec_result.stderr,
                    "fix_history": fix_history,
                    "attempts": max_retries + 1,
                },
            )

        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                error=str(e),
            )

    def _generate_code(self, plan: dict, spec: ProblemSpec | None) -> str:
        """根据建模方案生成代码"""
        # 有 API key 时调用 LLM 生成
        if self.config.llm.claude_api_key or self.config.llm.openai_api_key:
            return self._generate_with_llm(plan, spec)

        # 无 API key 时使用模板
        return self._generate_from_template(plan, spec)

    def _generate_with_llm(self, plan: dict, spec: ProblemSpec | None) -> str:
        """调用 LLM 生成代码"""
        best = plan.get("best_approach", "")
        problem_type = plan.get("problem_type", "")

        user_content = f"""请根据以下建模方案生成 Python 求解代码：

## 题目信息
- 标题: {spec.title if spec else '未知'}
- 问题类型: {problem_type}
- 描述: {spec.description[:500] if spec else '未知'}
- 目标: {spec.objective if spec else '未知'}

## 推荐方案
- 方案名称: {best}
- 原理: {self._get_approach_principle(plan, best)}

## 代码要求
1. 包含 solve() 主函数
2. 结果用 print 输出
3. 使用 numpy/scipy 等常见库
4. 可直接运行"""

        messages = [
            Message(role="system", content=CODE_SYSTEM_PROMPT),
            Message(role="user", content=user_content),
        ]

        raw = self.llm.chat(messages, temperature=0.2)
        return self._extract_code(raw)

    def _generate_from_template(self, plan: dict, spec: ProblemSpec | None) -> str:
        """从模板生成代码"""
        problem_type = plan.get("problem_type", "优化类")

        # 匹配模板
        for key in CODE_TEMPLATES:
            if key in problem_type or problem_type in key:
                return CODE_TEMPLATES[key]

        # 默认优化类
        return CODE_TEMPLATES["优化类"]

    def _fix_code(self, code: str, error: str, plan: dict, spec: ProblemSpec | None) -> str | None:
        """修复错误代码"""
        # 有 API key 时调用 LLM 修复
        if self.config.llm.claude_api_key or self.config.llm.openai_api_key:
            return self._fix_with_llm(code, error, plan, spec)

        # 无 API key 时使用简单修复
        return self._fix_simple(code, error)

    def _fix_with_llm(self, code: str, error: str, plan: dict, spec: ProblemSpec | None) -> str | None:
        """调用 LLM 修复代码"""
        user_content = f"""以下代码运行时出现错误，请修复：

## 代码
```python
{code}
```

## 错误信息
```
{error}
```

请输出修复后的完整代码。"""

        messages = [
            Message(role="system", content=FIX_SYSTEM_PROMPT),
            Message(role="user", content=user_content),
        ]

        try:
            raw = self.llm.chat(messages, temperature=0.1)
            fixed = self._extract_code(raw)
            if fixed and fixed != code:
                return fixed
        except Exception:
            pass
        return None

    def _fix_simple(self, code: str, error: str) -> str | None:
        """简单规则修复 (无 LLM 时)"""
        # 常见错误修复
        fixes = [
            # import 缺失
            (r"NameError: name '(\w+)' is not defined",
             lambda m: self._add_import(code, m.group(1))),
            # 缩进错误 - 无法自动修复
        ]

        for pattern, fix_fn in fixes:
            match = re.search(pattern, error)
            if match:
                return fix_fn(match)

        return None

    def _add_import(self, code: str, module: str) -> str:
        """自动添加缺失的 import"""
        import_map = {
            "np": "import numpy as np",
            "numpy": "import numpy as np",
            "plt": "import matplotlib.pyplot as plt",
            "pd": "import pandas as pd",
            "stats": "from scipy import stats",
            "optimize": "from scipy import optimize",
        }
        if module in import_map:
            imp = import_map[module]
            if imp not in code:
                return imp + "\n" + code
        return None

    def _extract_code(self, text: str) -> str:
        """从 LLM 响应中提取代码"""
        # 尝试提取 ```python ... ``` 代码块
        pattern = r"```(?:python)?\s*\n(.*?)\n\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 尝试提取 ``` ... ``` 代码块
        pattern = r"```\s*\n(.*?)\n\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        return text.strip()

    def _get_approach_principle(self, plan: dict, approach_name: str) -> str:
        """从方案列表中获取指定方案的原理"""
        for a in plan.get("approaches", []):
            if a.get("name") == approach_name:
                return a.get("principle", "")
        return ""

    def _extract_lesson(self, stderr: str) -> str:
        """从错误信息中提取经验教训"""
        if "ModuleNotFoundError" in stderr:
            module = re.search(r"No module named '([^']+)'", stderr)
            return f"缺少模块 {module.group(1) if module else '未知'}，需要检查 import"
        elif "ValueError" in stderr and "shapes" in stderr:
            return "矩阵维度不匹配，需要检查 dot/矩阵运算前的形状"
        elif "LinAlgError" in stderr:
            return "矩阵奇异，应改用 lstsq 或 pinv"
        elif "ZeroDivisionError" in stderr:
            return "除零错误，需要添加边界检查"
        elif "FileNotFoundError" in stderr:
            return "文件路径错误，应使用 Path(__file__).parent 构建路径"
        elif "TypeError" in stderr:
            return "类型错误，需要检查函数参数类型"
        elif "SyntaxError" in stderr:
            return "语法错误，需要检查括号匹配和缩进"
        return "运行时错误，需要检查代码逻辑"

    def _build_log(self, code: str, exec_result: ExecResult, fix_history: list, attempts: int) -> str:
        """构建执行日志"""
        lines = []
        lines.append("=" * 60)
        lines.append("Code Execution Agent - 执行日志")
        lines.append("=" * 60)
        lines.append(f"总尝试次数: {attempts + 1}")
        lines.append(f"最终状态: {'成功' if exec_result.success else '失败'}")
        lines.append("")

        lines.append("-" * 60)
        lines.append("执行输出:")
        lines.append("-" * 60)
        if exec_result.stdout:
            lines.append(exec_result.stdout)
        if exec_result.stderr:
            lines.append("STDERR:")
            lines.append(exec_result.stderr)

        if fix_history:
            lines.append("")
            lines.append("-" * 60)
            lines.append("错误修复记录:")
            lines.append("-" * 60)
            for record in fix_history:
                lines.append(f"第 {record['attempt']} 次尝试:")
                lines.append(f"  状态: {record['status']}")
                lines.append(f"  错误: {record['error'][:200]}")
                if record.get("lesson"):
                    lines.append(f"  经验: {record['lesson']}")
                lines.append("")

        return "\n".join(lines)
