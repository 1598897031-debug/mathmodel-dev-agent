---
description: Python 自动调试 — 运行代码、解析 traceback、自动修复、rerun
argument-hint: <python-file-or-command>
---

# Python Auto-Debug

运行 Python 代码，失败时自动解析 traceback 并修复。

**Input**: $ARGUMENTS

---

## Phase 1: RUN

```bash
python $ARGUMENTS 2>&1
```

如果成功，输出 "All good!" 并停止。

如果失败，进入 Phase 2。

## Phase 2: PARSE TRACEBACK

从 stderr 中提取：

1. **错误类型**: `ModuleNotFoundError`, `TypeError`, `ValueError` 等
2. **错误信息**: 具体的错误描述
3. **文件和行号**: 出错的位置
4. **完整调用栈**: 上下文

## Phase 3: CLASSIFY

| 错误类型 | 分类 | 修复策略 |
|---------|------|---------|
| ImportError / ModuleNotFoundError | 依赖缺失 | pip install |
| SyntaxError / IndentationError | 语法错误 | 修复代码 |
| TypeError / ValueError | 运行时错误 | 修复逻辑 |
| FileNotFoundError | 路径错误 | 修复路径 |
| KeyError / IndexError | 数据错误 | 修复索引 |
| LinAlgError | 数学错误 | 换算法 |
| subprocess 相关 | 环境错误 | 检查命令 |

## Phase 4: FIX

根据分类执行修复：

- **依赖缺失**: `pip install <module>`
- **语法/运行时错误**: 定位到具体行，使用 Edit 工具修复
- **科学计算错误**: 参考 `.claude/skills/python-debug/debug-patterns.md`

## Phase 5: RERUN

```bash
python $ARGUMENTS 2>&1
```

如果成功，输出修复报告。
如果失败，回到 Phase 2（最多 3 轮）。

## Phase 6: REPORT

```markdown
# Debug Report

**文件**: $ARGUMENTS
**尝试次数**: X/3

## 错误 1
- 类型: ModuleNotFoundError
- 信息: No module named 'numpy'
- 修复: pip install numpy
- 结果: PASS

## 错误 2 (如有)
- ...

## 最终状态: PASS / FAIL
```
