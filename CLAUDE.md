# MathModel Dev Agent - Claude Code 项目指引

## 项目概述

基于 Multi-Agent 的数学建模与自动开发系统。

Pipeline: `parser → strategy → code → experiment → paper → github`

运行: `python main.py <题目文件>`
测试: `pytest tests/`

---

## Skill 自动路由规则

**核心原则**: 根据上下文自动匹配 skill，不等用户手动输入命令。

### 触发条件速查表

| 场景 | 自动触发的 Skill | 触发方式 |
|------|-----------------|---------|
| 设计新 Agent / 架构变更 | planning-with-files `/plan` | 识别到架构设计意图时 |
| Python 代码执行失败 | python-debug `/pydebug` | 检测到 traceback 时 |
| 写完/修改 Python 代码 | ECC `/python-review` | 代码编辑完成后 |
| 构建/导入报错 | ECC `/build-fix` | 检测到编译/import 错误时 |
| Agent 间传递数据 | context-engineering | Orchestrator 更新 context 时 |
| CodeAgent 第 2 次重试 | context-engineering Reflexion | 同一错误重复出现时 |
| 提交前审查 | ECC `/code-review` | git commit 前 |
| 所有编码工作 | andrej-karpathy-skills | 始终生效 |

---

### Skill 1: planning-with-files

**触发条件** (满足任一即触发):

```
- 用户提到 "设计"、"架构"、"新增 Agent"、"重构"
- 需要修改 3 个以上文件
- 新增 Agent（新文件 + 测试 + 注册到 orchestrator）
- 修改 pipeline 顺序或 DAG 结构
- 设计新的数据结构（dataclass）
```

**触发方式**:

```
检测到上述场景 → 直接使用 /plan 命令的模式
不需要用户输入 /plan
```

**不触发**:

```
- 简单 bug 修复（改 1-2 行）
- 格式调整
- 文档更新
```

---

### Skill 2: python-debug

**触发条件** (满足任一即触发):

```
- bash 命令输出包含 "Traceback"、"Error"、"Exception"
- Python 代码执行返回非零退出码
- pytest 有失败用例
- ImportError / ModuleNotFoundError
- CodeAgent 执行循环中失败
```

**触发方式**:

```
检测到错误 → 解析 traceback → 分类 → 修复 → rerun
自动执行，不需要用户输入 /pydebug
```

**修复流程**:

```
1. 提取错误类型和行号
2. 分类: ImportError / SyntaxError / TypeError / ValueError / ...
3. 应用对应修复策略
4. Rerun 验证
5. 失败则重试（最多 3 次）
6. 超限则报告，不无限循环
```

**不触发**:

```
- 用户明确说 "不要修复"
- 逻辑错误（需要人工判断算法正确性）
- 数据本身的问题
```

---

### Skill 3: everything-claude-code (ECC)

#### /python-review

**触发条件**:

```
- 新建或修改 .py 文件后
- 函数超过 30 行
- 缺少类型注解
- 使用了 eval/exec
- 有 bare except
```

**触发方式**:

```
编辑完 Python 文件 → 自动审查变更部分
只审查 diff，不重新审查整个文件
```

#### /build-fix

**触发条件**:

```
- `python -m compileall` 失败
- `import` 语句报错
- 依赖缺失
- 语法错误
```

**触发方式**:

```
检测到编译/import 错误 → 自动修复
优先于 python-debug（先修复编译，再修复运行时）
```

#### /code-review

**触发条件**:

```
- 用户说 "审查"、"review"、"提交前检查"
- 修改了核心模块（agents/、core/、orchestrator.py）
- 准备 git commit
```

**触发方式**:

```
检测到上述场景 → 执行完整代码审查
```

---

### Skill 4: context-engineering

**触发条件** (满足任一即触发):

```
- Orchestrator._update_context() 被调用
- Agent 输出超过 2000 字符
- CodeAgent 第 2 次及以上重试
- 传递给下游 Agent 的数据超过 token 预算
```

**触发方式**:

```
Orchestrator 传递上下文 → 自动应用压缩/摘要
CodeAgent 重试 → 自动注入反思记录
```

**具体规则**:

```
ParserAgent → StrategyAgent:
  压缩: 仅保留 ProblemSpec 结构化字段
  删除: 原始题目文本

StrategyAgent → CodeAgent:
  摘要: 仅保留推荐方案的 name/principle/complexity
  删除: 所有候选方案详情

CodeAgent → ExperimentAgent:
  提取: stdout + 成功标志
  删除: 完整代码 + 生成日志

ExperimentAgent → PaperAgent:
  整合: metrics + plots + conclusion
  删除: 原始数据 + 中间计算
```

---

### Skill 5: andrej-karpathy-skills

**触发条件**: 始终生效

**核心规则**:

```
- Think before coding — 先理解再动手
- Simplicity first — 最简方案优先
- Surgical changes — 最小化改动
- Goal-driven — 每个改动都要有明确目的
- Don't over-engineer — 不过度设计
```

---

## 多 Skill 协同场景

### 场景 1: 处理新题目

```
用户输入: "解决这道优化题"
    │
    ├─ [始终] andrej-karpathy-skills → 简洁思考
    │
    ▼
ParserAgent 运行
    ├─ [context-engineering] 压缩长文本
    │
    ▼
StrategyAgent 运行
    ├─ [context-engineering] 摘要方案
    │
    ▼
CodeAgent 运行
    ├─ [python-debug] 失败时自动修复
    ├─ [context-engineering] Reflexion 记录
    ├─ [ECC /python-review] 代码写完后审查
    │
    ▼
ExperimentAgent 运行
    ├─ [python-debug] 绘图失败时修复
    │
    ▼
PaperAgent 运行
    ├─ [claude-office-skills] Word 导出
    │
    ▼
GitHubAgent 运行
    ├─ [ECC /code-review] 提交前审查
```

### 场景 2: 调试已有代码

```
用户说: "solution.py 报错了"
    │
    ├─ [python-debug] 解析 traceback
    ├─ [context-engineering] 如果是重复错误，注入反思
    │
    ▼
修复 → Rerun → 成功?
    ├─ [是] → [ECC /python-review] 审查修复后的代码
    ├─ [否] → 重试（最多 3 次）
```

### 场景 3: 新增 Agent

```
用户说: "添加一个数据清洗 Agent"
    │
    ├─ [planning-with-files /plan] 设计架构
    │   - 新 Agent 文件位置
    │   - 数据结构设计
    │   - 与现有 Agent 的接口
    │   - 测试计划
    │
    ▼
实现
    ├─ [andrej-karpathy-skills] 最小化改动
    ├─ [ECC /python-review] 代码审查
    ├─ [python-debug] 测试失败时修复
    │
    ▼
集成到 Orchestrator
    ├─ [ECC /build-fix] 修复导入问题
    ├─ [context-engineering] 更新上下文流
```

---

## Agent 协同规则

### 执行顺序（固定 DAG）

```
parser → strategy → code → experiment → paper → github
```

### 上下文传递

- ParserAgent 输出 `ProblemSpec` → StrategyAgent 接收
- StrategyAgent 输出 `ModelPlan` (dict) → CodeAgent 接收
- CodeAgent 输出 `ExecResult` (dict) → ExperimentAgent 接收
- ExperimentAgent 输出 `ExpResult` (dict) → PaperAgent 接收
- PaperAgent 输出论文文本 → GitHubAgent 接收

### 错误处理

- 每个 Agent 失败时，pipeline 停止，不跳过
- CodeAgent 有内置重试机制（最多 3 次）
- 所有 Agent 返回统一的 `AgentResult` 格式

---

## 开发规范

### 代码风格

- Python 3.10+
- 类型注解 (Type Hints)
- PEP 8
- dataclass 定义数据结构
- 公共函数添加 docstring

### 文件组织

```
mathmodel/
├── agents/          # 每个 Agent 一个文件
├── core/            # 共享组件
├── utils/           # 工具函数
├── templates/       # 模板文件
└── orchestrator.py  # Pipeline 编排
```

### 测试

- 每个 Agent 编写单元测试
- 测试文件: `tests/test_*.py`
- 框架: pytest
- 运行: `python -c "import tests.test_xxx"` 或 `pytest tests/`

---

## 已安装 Skills

| Skill | 来源 | 自动触发 | 用途 |
|-------|------|---------|------|
| python-debug | 项目级 | ✅ traceback 时 | 自动调试 + rerun |
| context-engineering | 项目级 | ✅ Agent 间传递时 | 上下文压缩 + Reflexion |
| everything-claude-code | 全局 | ✅ 代码变更后 | review / build-fix |
| planning-with-files | 全局 | ✅ 架构设计时 | 持久化规划 |
| andrej-karpathy-skills | 全局 | ✅ 始终 | 行为规范 |
| claude-office-skills | 全局 | 按需 | Word 导出 |

---

## 注意事项

1. API 密钥通过环境变量配置，不要硬编码
2. 代码执行使用子进程沙箱，防止无限循环
3. 所有 Agent 输出使用统一的 AgentResult 格式
4. 错误处理要完善，确保流程可恢复
5. 不要安装额外的 skill，当前组合已足够
6. 修改 Agent 前先验证导入: `python -c "from mathmodel.agents.xxx import XxxAgent; print('ok')"`
