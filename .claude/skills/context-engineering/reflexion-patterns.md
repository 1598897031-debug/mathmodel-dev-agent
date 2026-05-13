# Reflexion Patterns for MathModel Dev Agent

## Pattern 1: CodeAgent 调试反思

```python
# 每次调试失败后，生成反思记录
def generate_reflexion(error: str, fix: str, code: str) -> dict:
    """
    分析错误和修复，提取经验教训。

    Returns:
        {"error_type": str, "root_cause": str, "fix_pattern": str, "lesson": str}
    """
    # 错误类型分类
    error_type = classify_error(error)

    # 根因分析
    root_cause = analyze_root_cause(error, code)

    # 修复模式
    fix_pattern = extract_fix_pattern(fix)

    # 经验教训
    lesson = f"当遇到 {error_type} 时，应该 {fix_pattern}"

    return {
        "error_type": error_type,
        "root_cause": root_cause,
        "fix_pattern": fix_pattern,
        "lesson": lesson,
    }

# 错误类型分类
ERROR_CLASSIFICATION = {
    "ImportError": "依赖问题",
    "ModuleNotFoundError": "依赖问题",
    "SyntaxError": "语法问题",
    "IndentationError": "语法问题",
    "TypeError": "类型问题",
    "ValueError": "数值问题",
    "KeyError": "数据问题",
    "IndexError": "数据问题",
    "FileNotFoundError": "路径问题",
    "LinAlgError": "数学问题",
    "ZeroDivisionError": "数值问题",
}

# 修复模式库
FIX_PATTERNS = {
    "依赖问题": "在文件开头检查并安装缺失模块",
    "语法问题": "检查括号匹配、缩进、冒号",
    "类型问题": "添加类型转换或检查函数签名",
    "数值问题": "添加边界检查、处理 NaN/Inf",
    "数据问题": "使用 .get() 默认值或检查索引范围",
    "路径问题": "使用 Path(__file__).parent 构建路径",
    "数学问题": "换用更稳定的算法（如 lstsq 代替 solve）",
}
```

## Pattern 2: StrategyAgent 方案反思

```python
# 当推荐方案执行失败时，反思方案选择
def reflect_on_strategy(plan: dict, execution_result: dict) -> dict:
    """
    分析方案失败原因，调整推荐。

    Returns:
        {"failed_approach": str, "reason": str, "alternative": str}
    """
    failed = plan.get("best_approach", "")
    error = execution_result.get("stderr", "")

    # 判断是否是方案本身的问题
    if "LinAlgError" in error:
        return {
            "failed_approach": failed,
            "reason": "矩阵奇异，方案不适合",
            "alternative": "改用最小二乘法或正则化",
        }
    elif "TimeLimit" in error or "timeout" in error.lower():
        return {
            "failed_approach": failed,
            "reason": "计算复杂度过高",
            "alternative": "改用启发式算法或简化模型",
        }

    return {"failed_approach": failed, "reason": "未知", "alternative": "尝试下一方案"}
```

## Pattern 3: ExperimentAgent 结果反思

```python
# 当实验指标不佳时，反思模型质量
def reflect_on_experiment(metrics: dict) -> dict:
    """
    分析实验指标，给出改进建议。

    Returns:
        {"quality": str, "issues": list, "improvements": list}
    """
    r2 = metrics.get("r_squared", 0)
    rmse = metrics.get("rmse", float("inf"))
    mape = metrics.get("mape", float("inf"))

    quality = "excellent" if r2 > 0.9 else "good" if r2 > 0.7 else "moderate" if r2 > 0.5 else "poor"

    issues = []
    improvements = []

    if r2 < 0.5:
        issues.append("模型拟合效果差")
        improvements.append("尝试非线性模型或增加特征")
    if mape > 20:
        issues.append("预测误差较大")
        improvements.append("检查数据质量或调整模型参数")
    if rmse > 100:
        issues.append("均方根误差过大")
        improvements.append("进行数据标准化或归一化")

    return {"quality": quality, "issues": issues, "improvements": improvements}
```

## 使用方式

### 在 CodeAgent 中

```python
# code_agent.py 的重试循环中
if attempt > 1:
    # 注入之前的反思
    reflexion_context = "\n".join([
        f"- 第 {r['attempt']} 次: {r['lesson']}"
        for r in self.reflexion_log
    ])
    prompt += f"\n\n## 之前的经验教训\n{reflexion_context}\n\n请避免重复这些错误。"
```

### 在 Orchestrator 中

```python
# orchestrator.py 中传递反思
if agent_name == "code" and not result.success:
    # 记录反思供下次使用
    self.reflexion_log.append({
        "agent": "code",
        "error": result.error,
        "context": context.problem_spec.title if context.problem_spec else "",
    })
```
