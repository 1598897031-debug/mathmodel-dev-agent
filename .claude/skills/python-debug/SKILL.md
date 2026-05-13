---
name: python-debug
description: Python 自动调试技能。解析 traceback、定位根因、自动修复、安装缺失依赖、rerun。专门适配科学计算项目（numpy/scipy/matplotlib/pandas）。
globs: ["**/*.py"]
alwaysApply: false
---

# Python Auto-Debug Skill

自动运行 Python 代码 → 捕获 traceback → 解析根因 → 修复 → 安装依赖 → rerun，直到成功或达到重试上限。

## When to Activate

- Python 代码执行失败时
- CodeAgent 生成代码后验证失败
- ExperimentAgent 运行出错
- 手动 `python xxx.py` 报错
- `pytest` 测试失败

## 核心流程

```
运行代码 → 成功? → [是] → 完成
              ↓ [否]
         解析 traceback
              ↓
         分类错误类型
              ↓
    ┌─────────┼─────────┐
    ↓         ↓         ↓
 ImportError  Syntax   Runtime
    ↓         ↓         ↓
 安装依赖   修复语法  修复逻辑
    ↓         ↓         ↓
    └─────────┼─────────┘
              ↓
         Rerun 验证
              ↓
         成功? → [是] → 完成
              ↓ [否]
         重试 (最多 3 次)
              ↓
         超限 → 报告失败
```

## 错误分类与修复策略

### 1. ImportError / ModuleNotFoundError

**检测模式**:
```
ModuleNotFoundError: No module named 'xxx'
ImportError: cannot import name 'xxx' from 'yyy'
```

**修复策略**:
```bash
# 科学计算库
pip install numpy scipy matplotlib pandas sympy statsmodels scikit-learn

# 其他常见库
pip install <module_name>

# 特定版本
pip install "numpy>=1.24.0"
```

**科学计算库映射**:
| 缺失模块 | 安装命令 | 常见用途 |
|----------|---------|---------|
| numpy | `pip install numpy` | 数组计算 |
| scipy | `pip install scipy` | 科学计算、优化、统计 |
| matplotlib | `pip install matplotlib` | 绘图 |
| pandas | `pip install pandas` | 数据处理 |
| sympy | `pip install sympy` | 符号计算 |
| sklearn | `pip install scikit-learn` | 机器学习 |
| statsmodels | `pip install statsmodels` | 统计模型 |
| seaborn | `pip install seaborn` | 统计可视化 |
| PIL/Pillow | `pip install Pillow` | 图像处理 |

### 2. SyntaxError

**检测模式**:
```
SyntaxError: invalid syntax
SyntaxError: unexpected EOF while parsing
IndentationError: unexpected indent
```

**修复策略**:
- 定位到报错行号
- 检查括号匹配、缩进、冒号
- 修复后 rerun

### 3. TypeError / ValueError

**检测模式**:
```
TypeError: unsupported operand type(s)
TypeError: missing required argument
ValueError: shapes not aligned
ValueError: array must not contain infs or NaNs
```

**修复策略**:
- 检查函数签名和参数类型
- 检查数组维度匹配
- 添加类型转换 `float()`, `int()`, `np.array()`
- 处理 NaN/Inf: `np.nan_to_num()`

### 4. FileNotFoundError / PermissionError

**检测模式**:
```
FileNotFoundError: [Errno 2] No such file or directory
PermissionError: [Errno 13] Permission denied
```

**修复策略**:
- 检查文件路径是否正确
- 使用 `Path(__file__).parent` 构建相对路径
- 确保目录存在: `path.mkdir(parents=True, exist_ok=True)`

### 5. KeyError / IndexError

**检测模式**:
```
KeyError: 'xxx'
IndexError: list index out of range
```

**修复策略**:
- 检查字典键名是否正确
- 添加 `.get()` 默认值
- 检查数组越界

### 6. subprocess 相关错误

**检测模式**:
```
subprocess.TimeoutExpired
FileNotFoundError: [Errno 2] No such file or directory: 'git'
```

**修复策略**:
- 检查外部命令是否安装
- 增加 timeout
- 使用 `capture_output=True`

## 调用方式

### 方式 1: 自动触发（CodeAgent 集成）

当 CodeAgent 执行代码失败时，自动调用本 skill：

```python
# CodeAgent 内部调用
from mathmodel.agents.code_agent import CodeAgent

# 执行失败后，自动进入 debug 循环
# 1. 解析 stderr 中的 traceback
# 2. 分类错误类型
# 3. 应用修复策略
# 4. Rerun
```

### 方式 2: 手动触发

```bash
# 运行代码并自动调试
python code/solution.py 2>&1

# 如果失败，在 Claude Code 中：
/debug python code/solution.py
```

### 方式 3: pytest 集成

```bash
# 运行测试并自动修复失败用例
pytest tests/ -v

# 如果有失败：
/debug pytest tests/ -v
```

## 修复模板

### 模板 1: 缺失依赖修复

```python
# 问题: ModuleNotFoundError: No module named 'numpy'
# 修复: 安装依赖
import subprocess
subprocess.run(["pip", "install", "numpy"], capture_output=True)
import numpy as np  # 重试导入
```

### 模板 2: 数组维度修复

```python
# 问题: ValueError: shapes not aligned
# 修复: 检查并重塑数组
import numpy as np
a = np.asarray(a).flatten()
b = np.asarray(b).flatten()
assert len(a) == len(b), f"维度不匹配: {len(a)} vs {len(b)}"
```

### 模板 3: 文件路径修复

```python
# 问题: FileNotFoundError
# 修复: 使用项目根目录构建路径
from pathlib import Path
PROJECT_DIR = Path(__file__).parent.parent
data_file = PROJECT_DIR / "data" / "input.csv"
assert data_file.exists(), f"文件不存在: {data_file}"
```

### 模板 4: NaN/Inf 处理

```python
# 问题: ValueError: array must not contain infs or NaNs
# 修复: 清洗数据
import numpy as np
data = np.nan_to_num(data, nan=0.0, posinf=np.finfo(float).max, neginf=np.finfo(float).min)
```

## 与 Agent 的协同方式

### CodeAgent 集成

```
CodeAgent 生成代码
    ↓
执行 solution.py
    ↓ (失败)
python-debug skill 接管
    ↓
解析 traceback → 分类 → 修复
    ↓
Rerun solution.py
    ↓ (成功)
继续 pipeline
    ↓ (失败 x3)
报告最终失败 + 错误详情
```

### ExperimentAgent 集成

```
ExperimentAgent 运行实验
    ↓ (失败)
python-debug skill 接管
    ↓
解析科学计算错误（维度/NaN/精度）
    ↓
修复数据处理代码
    ↓
Rerun 实验
```

### 与 RIPER Workflow 的协同

| RIPER 阶段 | python-debug 的角色 |
|-----------|---------------------|
| Research | 不参与 |
| Innovate | 不参与 |
| Plan | 不参与 |
| **Execute** | **核心角色** — 代码执行失败时自动修复 |
| **Review** | **辅助角色** — 验证修复后的代码通过测试 |

## 排除模式

以下情况**不自动修复**，而是报告给用户：

1. **逻辑错误** — 算法本身有问题（需要人工判断）
2. **数据错误** — 输入数据格式不正确
3. **环境问题** — Python 版本不兼容
4. **权限问题** — 需要管理员权限
5. **网络问题** — API 调用失败
6. **超过重试上限** — 3 次修复尝试后仍失败

## 配置

在 `mathmodel/config.py` 中可配置：

```python
@dataclass
class ExecutorConfig:
    timeout: int = 30           # 单次执行超时 (秒)
    max_retries: int = 3        # 最大重试次数
    auto_debug: bool = True     # 是否启用自动调试
    install_deps: bool = True   # 是否自动安装缺失依赖
```

## 成功标准

- 首次修复成功率 > 70%
- 平均修复轮次 < 2 次
- 不引入新的错误
- 修复时间 < 30 秒/次

---

*Part of MathModel Dev Agent*
