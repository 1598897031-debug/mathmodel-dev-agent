---
name: context-engineering
description: 多 Agent 上下文工程技术。覆盖上下文压缩、Reflexion 自我反思、跨 Agent 摘要、长文本管理。专为数学建模 Multi-Agent 系统设计。
globs: ["**/*.py", "**/*.md"]
alwaysApply: false
---

# Context Engineering for Multi-Agent Systems

为 MathModel Dev Agent 定制的上下文工程技术，解决多 Agent 之间的信息传递、压缩和反思问题。

## 核心技术

### 1. 上下文压缩 (Context Compression)

**问题**: ParserAgent 解析长题目时，原始文本可能超过 token 限制。

**方案**: 智能摘要，保留关键信息。

```python
def compress_problem_text(text: str, max_tokens: int = 2000) -> str:
    """
    压缩题目文本，保留关键信息:
    - 变量定义 (x, y, z)
    - 约束条件 (<=, >=, =)
    - 目标函数 (maximize, minimize)
    - 数字数据 (具体数值)
    删除: 例子、重复描述、格式文本
    """
    # 保留行: 包含变量名、约束符号、目标词
    # 删除行: 纯叙述、重复、格式
    pass
```

**调用时机**: ParserAgent 接收 > 3000 字符的题目文本时。

### 2. Reflexion 自我反思

**问题**: CodeAgent 调试循环中重复犯同样的错误。

**方案**: 每次失败后记录反思，下次避免。

```python
# Reflexion 记录格式
reflexion_entry = {
    "attempt": 2,
    "error": "ValueError: shapes not aligned",
    "root_cause": "矩阵 A 是 (3,4) 但向量 b 是 (3,)",
    "fix_applied": "转置 A 为 (4,3) 或重塑 b 为 (4,)",
    "lesson": "dot 操作前检查维度匹配",
    "avoid_next_time": "生成代码时自动添加 assert 维度检查",
}
```

**调用时机**: CodeAgent 同一错误第 2 次出现时。

### 3. 跨 Agent 摘要 (Cross-Agent Summarization)

**问题**: Agent 之间传递完整输出会浪费 token。

**方案**: 为下游 Agent 生成定制摘要。

```python
# 摘要映射
SUMMARY_MAP = {
    "parser → strategy": {
        "keep": ["problem_type", "variables", "constraints", "objective"],
        "drop": ["raw_text", "description_full"],
    },
    "strategy → code": {
        "keep": ["best_approach", "principle", "required_tools"],
        "drop": ["all_approaches", "pros_cons_full"],
    },
    "code → experiment": {
        "keep": ["stdout", "stderr", "success"],
        "drop": ["full_code", "generation_log"],
    },
    "experiment → paper": {
        "keep": ["metrics", "plots", "conclusion"],
        "drop": ["raw_data", "intermediate_calculations"],
    },
}
```

**调用时机**: Orchestrator 在 `_update_context()` 中自动应用。

### 4. 长对话管理

**问题**: 单个 Agent 内部对话过长（如 CodeAgent 多轮调试）。

**方案**: 滑动窗口 + 关键信息保留。

```
策略:
- 保留最近 3 轮对话
- 保留首次成功的代码版本
- 保留所有错误的反思记录
- 压缩中间调试过程
```

## 在项目中的应用

### Agent 间上下文流

```
ParserAgent 输出 (完整 ProblemSpec)
    ↓ [压缩: 仅保留结构化字段]
StrategyAgent 输入 (精简 ProblemSpec)
    ↓ [摘要: 仅保留推荐方案]
CodeAgent 输入 (方案要点 + 约束)
    ↓ [Reflexion: 记录失败经验]
ExperimentAgent 输入 (执行结果 + 反思)
    ↓ [整合: 指标 + 图表 + 结论]
PaperAgent 输入 (全部精华)
```

### Orchestrator 集成

在 `orchestrator.py` 的 `_update_context()` 中应用:

```python
def _update_context(self, context, agent_name, output):
    if agent_name == "parser":
        # 压缩: 只保留结构化字段
        context.problem_spec = self._compress_spec(output)
    elif agent_name == "strategy":
        # 摘要: 只保留推荐方案
        context.model_plan = self._summarize_plan(output)
    # ...
```

### CodeAgent Reflexion 集成

在 `code_agent.py` 的重试循环中应用:

```python
# 每次失败后记录反思
self.reflexion_log.append({
    "error": stderr[:200],
    "fix": "修复描述",
    "lesson": "经验教训",
})

# 生成代码时注入反思
if self.reflexion_log:
    prompt += "\n## 之前的经验教训\n"
    for entry in self.reflexion_log[-3:]:
        prompt += f"- {entry['lesson']}\n"
```

## Token 预算管理

| Agent | 输入预算 | 输出预算 | 策略 |
|-------|---------|---------|------|
| ParserAgent | 4000 tokens | 500 tokens | 压缩原始文本 |
| StrategyAgent | 1000 tokens | 800 tokens | 知识库匹配 |
| CodeAgent | 1500 tokens | 2000 tokens | 注入反思 |
| ExperimentAgent | 1000 tokens | 500 tokens | 仅传递指标 |
| PaperAgent | 2000 tokens | 3000 tokens | 整合全部 |
| GitHubAgent | 1000 tokens | 500 tokens | 生成文档 |

## 排除模式

以下场景**不应用**上下文工程:

1. **首次运行** — 保留完整信息，不压缩
2. **调试模式** — 保留完整 traceback，不摘要
3. **用户请求完整输出** — 尊重用户意图
4. **论文生成** — PaperAgent 需要完整信息

## 成功标准

- Agent 间信息丢失率 < 5%
- Token 消耗减少 > 30%
- CodeAgent 重复错误率下降 > 50%
- Pipeline 总耗时减少 > 10%

---

*Part of MathModel Dev Agent*
