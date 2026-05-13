# MathModel Dev Agent

基于 Multi-Agent 的数学建模与自动开发系统。

## 功能特性

- **问题解析 Agent**: 自动解析 PDF/TXT 格式的数学建模题目
- **建模策略 Agent**: 生成多个建模方案并推荐最佳路线
- **代码执行 Agent**: 自动生成 Python 求解代码并执行
- **实验分析 Agent**: 自动做实验、绘图、结果分析
- **论文写作 Agent**: 自动生成数学建模论文框架
- **GitHub 自动化 Agent**: 自动生成 README、git commit 和 push

## 安装

```bash
# 克隆项目
git clone https://github.com/your-username/mathmodel-dev-agent.git
cd mathmodel-dev-agent

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API 密钥
```

## 使用方法

```bash
# 基本用法
python main.py examples/sample_optimization.txt

# 指定项目名称
python main.py examples/sample_prediction.txt --project-name 人口预测

# 启用详细输出
python main.py problem.pdf --verbose

# 启用调试模式
python main.py problem.txt --debug
```

## 项目结构

```
mathmodel-dev-agent/
├── mathmodel/                    # 核心代码
│   ├── agents/                   # 六大 Agent
│   ├── core/                     # 共享基础设施
│   ├── templates/                # Prompt 和文档模板
│   └── utils/                    # 工具函数
├── projects/                     # 项目输出目录
├── examples/                     # 示例题目
├── tests/                        # 测试文件
├── main.py                       # 主入口
├── requirements.txt              # 依赖清单
└── .env.example                  # 环境变量示例
```

## 开发阶段

### Phase 1: 基础设施 ✅
- [x] 项目结构搭建
- [x] 配置管理
- [x] LLM 客户端
- [x] 代码执行沙箱

### Phase 2: 核心 Agent (开发中)
- [ ] 问题解析 Agent
- [ ] 建模策略 Agent
- [ ] 代码执行 Agent

### Phase 3: 输出 Agent
- [ ] 实验分析 Agent
- [ ] 论文写作 Agent
- [ ] GitHub 自动化 Agent

### Phase 4: 集成测试
- [ ] 端到端测试
- [ ] 错误处理完善
- [ ] 文档编写

## 许可证

MIT License
