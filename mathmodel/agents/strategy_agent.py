"""
建模策略 Agent (Model Strategy Agent)
根据 ProblemSpec 自动生成多个建模方案并推荐最佳路线
支持预测类、优化类、路径规划、统计分析四大类问题
"""

import json
import re
from dataclasses import dataclass, field

from ..core.llm_client import LLMClient, Message
from ..core.document_parser import ProblemSpec
from ..config import AppConfig
from .base import BaseAgent, AgentContext, AgentResult

# ==================== System Prompt ====================

STRATEGY_SYSTEM_PROMPT = """\
你是一个数学建模策略专家。根据给定的数学建模题目，生成多个建模方案并推荐最佳路线。

请严格按照以下 JSON 格式输出，不要添加任何额外解释：

{
  "problem_type": "题目类型（预测类/优化类/路径规划类/统计类/其他）",
  "problem_summary": "题目核心问题的一句话概括",
  "approaches": [
    {
      "name": "方案名称（如：线性规划法、灰色预测法等）",
      "principle": "方案的基本原理和数学方法描述（2-3句话）",
      "pros": ["优点1", "优点2", "优点3"],
      "cons": ["缺点1", "缺点2"],
      "complexity": "低/中/高",
      "competition_suitability": "高/中/低（数学建模比赛适用性）",
      "required_tools": ["需要的Python库或工具"]
    }
  ],
  "best_approach": "最佳方案名称",
  "recommendation_reason": "推荐该方案的理由（为什么最适合这道题）"
}

要求：
1. 至少给出 3 个不同方案
2. 方案之间应有明显差异（不同数学方法）
3. 每个方案的 pros 至少 2 条，cons 至少 1 条
4. complexity 和 competition_suitability 从 低/中/高 中选择
5. 只输出 JSON，不要输出其他内容"""

# ==================== Fallback 知识库 ====================

KNOWLEDGE_BASE = {
    "预测类": [
        {
            "name": "灰色预测 GM(1,1)",
            "principle": "灰色系统理论的核心方法，通过对原始数据进行累加生成，建立微分方程模型。适用于小样本、贫信息的不确定性系统预测。",
            "pros": ["样本量要求低（4个以上数据点即可）", "计算简单，易于实现", "对指数增长趋势预测效果好"],
            "cons": ["仅适用于单调变化序列", "对波动数据预测效果差", "长期预测精度下降"],
            "complexity": "低",
            "competition_suitability": "高",
            "required_tools": ["numpy"],
        },
        {
            "name": "多元线性回归",
            "principle": "建立因变量与多个自变量之间的线性关系模型，通过最小二乘法估计参数。可进行变量显著性检验和拟合优度分析。",
            "pros": ["理论成熟，结果可解释性强", "可同时分析多个影响因素", "提供统计检验指标"],
            "cons": ["要求变量间线性关系", "对异常值敏感", "多重共线性问题"],
            "complexity": "低",
            "competition_suitability": "高",
            "required_tools": ["numpy", "scipy", "statsmodels"],
        },
        {
            "name": "时间序列 ARIMA",
            "principle": "自回归积分滑动平均模型，通过差分将非平稳序列转化为平稳序列，利用自相关和偏自相关函数确定模型阶数。",
            "pros": ["经典时间序列方法", "有成熟的定阶准则（AIC/BIC）", "短期预测精度高"],
            "cons": ["要求数据平稳或可差分平稳", "对突变数据敏感", "需要较多历史数据"],
            "complexity": "中",
            "competition_suitability": "高",
            "required_tools": ["statsmodels", "pandas"],
        },
        {
            "name": "BP 神经网络",
            "principle": "反向传播神经网络，通过多层感知机拟合非线性映射关系。具有强大的非线性拟合能力，适用于复杂系统的预测。",
            "pros": ["非线性拟合能力强", "不需要预设函数形式", "可处理多输入多输出"],
            "cons": ["需要较多训练数据", "容易过拟合", "结果不可解释（黑箱）"],
            "complexity": "中",
            "competition_suitability": "中",
            "required_tools": ["numpy", "scikit-learn 或 tensorflow/pytorch"],
        },
    ],
    "优化类": [
        {
            "name": "线性规划 (LP)",
            "principle": "在线性约束条件下，求解线性目标函数的最优值。使用单纯形法或内点法求解，是运筹学的基础方法。",
            "pros": ["理论完善，求解高效", "有成熟求解器（scipy, cvxpy）", "全局最优解保证"],
            "cons": ["仅适用于线性问题", "约束必须是线性的", "实际问题常需要线性化近似"],
            "complexity": "低",
            "competition_suitability": "高",
            "required_tools": ["scipy.optimize", "cvxpy"],
        },
        {
            "name": "整数规划 / 混合整数规划",
            "principle": "在 LP 基础上增加决策变量为整数的约束。使用分支定界法、割平面法等求解。适用于资源分配、调度等离散决策问题。",
            "pros": ["处理离散决策问题", "结果可直接执行", "可建模逻辑约束"],
            "cons": ["求解复杂度高（NP-hard）", "大规模问题求解慢", "需要专用求解器"],
            "complexity": "中",
            "competition_suitability": "高",
            "required_tools": ["cvxpy", "pulp", "gurobipy"],
        },
        {
            "name": "非线性规划 (NLP)",
            "principle": "目标函数或约束中包含非线性项的优化问题。使用梯度下降、牛顿法、SQP 等算法求解。",
            "pros": ["可建模真实非线性关系", "适用范围广", "可处理复杂约束"],
            "cons": ["可能陷入局部最优", "对初值敏感", "求解速度较慢"],
            "complexity": "中",
            "competition_suitability": "高",
            "required_tools": ["scipy.optimize", "numpy"],
        },
        {
            "name": "智能优化算法 (GA/PSO/SA)",
            "principle": "模仿自然进化或物理过程的元启发式算法。遗传算法(GA)模拟生物进化，粒子群算法(PSO)模拟鸟群行为，模拟退火(SA)模拟金属退火。",
            "pros": ["全局搜索能力强", "不需要梯度信息", "可处理复杂约束和黑箱函数"],
            "cons": ["不保证全局最优", "参数调优困难", "计算开销大"],
            "complexity": "中",
            "competition_suitability": "中",
            "required_tools": ["numpy", "scipy", "deap 或自实现"],
        },
    ],
    "路径规划类": [
        {
            "name": "Dijkstra 最短路径算法",
            "principle": "图论经典算法，从起点出发，每次选择距离最近的未访问节点进行扩展，直到到达终点。保证找到最短路径。",
            "pros": ["保证全局最优", "时间复杂度可接受 O(V^2 或 VlogV)", "实现简单"],
            "cons": ["仅适用于非负权重图", "不适用于动态变化的图", "大规模图效率较低"],
            "complexity": "低",
            "competition_suitability": "高",
            "required_tools": ["networkx", "heapq"],
        },
        {
            "name": "A* 搜索算法",
            "principle": "在 Dijkstra 基础上引入启发式函数估计剩余距离，优先探索最有希望的节点。兼顾最优性和效率。",
            "pros": ["比 Dijkstra 更高效", "启发式加速搜索", "保证最优解（启发式一致时）"],
            "cons": ["启发式函数设计影响性能", "内存消耗较大", "不适合高维空间"],
            "complexity": "低",
            "competition_suitability": "高",
            "required_tools": ["heapq", "numpy"],
        },
        {
            "name": "遗传算法求解 TSP",
            "principle": "将路径编码为染色体，通过选择、交叉、变异操作进化种群，逐步逼近最优路径。适用于旅行商问题等组合优化。",
            "pros": ["可处理 NP-hard 问题", "全局搜索能力强", "可加入各种约束"],
            "cons": ["不保证最优解", "收敛速度慢", "编码方式影响效果"],
            "complexity": "中",
            "competition_suitability": "中",
            "required_tools": ["numpy", "random"],
        },
        {
            "name": "蚁群算法",
            "principle": "模拟蚂蚁觅食行为，通过信息素积累和挥发机制引导搜索。适用于离散组合优化和路径规划问题。",
            "pros": ["正反馈机制提高搜索效率", "分布式计算", "可处理动态问题"],
            "cons": ["收敛速度慢", "容易陷入局部最优", "参数敏感"],
            "complexity": "中",
            "competition_suitability": "中",
            "required_tools": ["numpy", "random"],
        },
    ],
    "统计类": [
        {
            "name": "假设检验 (t检验/卡方检验)",
            "principle": "通过样本数据对总体参数或分布进行推断。t检验用于均值比较，卡方检验用于独立性和拟合优度检验。",
            "pros": ["统计理论完善", "结果有明确的置信度", "适用范围广"],
            "cons": ["需要满足正态性等前提假设", "对样本量有要求", "仅能检验已有假设"],
            "complexity": "低",
            "competition_suitability": "高",
            "required_tools": ["scipy.stats", "numpy"],
        },
        {
            "name": "方差分析 (ANOVA)",
            "principle": "分析多个组别之间均值差异的显著性。通过分解总变异为组间变异和组内变异，判断因素影响是否显著。",
            "pros": ["可同时比较多组", "可分析交互效应", "结果易于解释"],
            "cons": ["要求正态性和方差齐性", "仅能判断是否有差异", "不能确定差异方向"],
            "complexity": "低",
            "competition_suitability": "高",
            "required_tools": ["scipy.stats", "statsmodels"],
        },
        {
            "name": "多元回归分析",
            "principle": "建立多个自变量与因变量之间的定量关系。可进行变量选择、多重共线性诊断、残差分析等。",
            "pros": ["可量化变量关系", "提供预测模型", "可进行变量筛选"],
            "cons": ["要求线性关系", "多重共线性影响", "异常值敏感"],
            "complexity": "低",
            "competition_suitability": "高",
            "required_tools": ["numpy", "scipy", "statsmodels"],
        },
        {
            "name": "聚类分析 (K-means/层次聚类)",
            "principle": "无监督学习方法，将数据自动分组。K-means 通过迭代优化聚类中心，层次聚类通过距离度量构建聚类树。",
            "pros": ["无需标签数据", "可发现数据结构", "结果可视化方便"],
            "cons": ["K值需要预设（K-means）", "对噪声敏感", "结果受初始化影响"],
            "complexity": "低",
            "competition_suitability": "中",
            "required_tools": ["scikit-learn", "numpy", "matplotlib"],
        },
    ],
}

# ==================== Agent 实现 ====================


class StrategyAgent(BaseAgent):
    """
    建模策略 Agent
    输入: ProblemSpec (解析后的题目)
    输出: 多个建模方案 + 推荐排序
    """

    name = "strategy"

    def run(self, context: AgentContext) -> AgentResult:
        """
        执行建模策略生成

        流程:
        1. 分析题目类型和约束
        2. 调用 LLM 生成方案 或 使用 fallback 知识库
        3. 解析响应为结构化数据
        4. 返回方案列表 + 推荐
        """
        try:
            if not context.problem_spec:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    error="缺少题目信息 (ProblemSpec)",
                )

            spec = context.problem_spec

            # 尝试 LLM 生成
            plan = self._generate_with_llm(spec)

            return AgentResult(
                success=True,
                agent_name=self.name,
                output=plan,
                metadata={"problem_type": spec.problem_type},
            )

        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                error=str(e),
            )

    def _generate_with_llm(self, spec: ProblemSpec) -> dict:
        """调用 LLM 生成建模方案"""
        # 检查 API key
        if not self.config.llm.claude_api_key and not self.config.llm.openai_api_key:
            return self._generate_fallback(spec)

        messages = self.build_prompt(spec)
        raw_response = self.llm.chat(messages, temperature=0.3)
        plan = self.parse_response(raw_response)

        # 补充原始题目信息
        plan["problem_spec_summary"] = {
            "title": spec.title,
            "problem_type": spec.problem_type,
            "objective": spec.objective,
        }
        return plan

    def _generate_fallback(self, spec: ProblemSpec) -> dict:
        """
        无 API key 时的 fallback 方案
        根据题目类型从知识库中选取推荐方案
        """
        problem_type = spec.problem_type or "其他"

        # 尝试匹配知识库中的类型
        # 使用更健壮的匹配逻辑：检查问题类型字符串是否包含关键字
        matched_type = None
        problem_type_lower = problem_type.lower()

        # 定义匹配规则
        type_mapping = {
            "预测类": ["预测", "prediction", "forecast"],
            "优化类": ["优化", "optimization", "linear"],
            "路径规划类": ["路径", "path", "route", "规划"],
            "统计类": ["统计", "statistic", "test", "检验"],
        }

        for ptype, keywords in type_mapping.items():
            for kw in keywords:
                if kw in problem_type_lower:
                    matched_type = ptype
                    break
            if matched_type:
                break

        # 如果没匹配到（包括"待分类"等情况），根据题目内容关键词推断
        if not matched_type:
            # 从题目描述中提取关键词进行推断
            desc_lower = (spec.description or "").lower()
            if any(kw in desc_lower for kw in ["预测", "prediction", "forecast", "人口"]):
                matched_type = "预测类"
            elif any(kw in desc_lower for kw in ["优化", "optimization", "最大", "最小", "利润"]):
                matched_type = "优化类"
            elif any(kw in desc_lower for kw in ["路径", "path", "route", "最短"]):
                matched_type = "路径规划类"
            elif any(kw in desc_lower for kw in ["统计", "statistic", "检验", "方差"]):
                matched_type = "统计类"
            else:
                matched_type = "优化类"

        approaches = KNOWLEDGE_BASE.get(matched_type, KNOWLEDGE_BASE["优化类"])

        # 标记推荐方案（第一个）
        approaches_with_flag = []
        for i, a in enumerate(approaches):
            item = dict(a)
            item["recommended"] = (i == 0)
            approaches_with_flag.append(item)

        return {
            "problem_type": matched_type,
            "problem_summary": f"{spec.title} - {spec.objective}" if spec.objective else spec.title,
            "approaches": approaches_with_flag,
            "best_approach": approaches[0]["name"],
            "recommendation_reason": f"基于题目类型[{matched_type}]推荐，{approaches[0]['name']}最为适合",
            "problem_spec_summary": {
                "title": spec.title,
                "problem_type": spec.problem_type,
                "objective": spec.objective,
            },
            "source": "fallback_knowledge_base",
        }

    def build_prompt(self, spec: ProblemSpec) -> list[Message]:
        """构建 LLM prompt"""
        user_content = f"""请为以下数学建模题目生成建模方案：

## 题目信息
- 标题: {spec.title}
- 问题类型: {spec.problem_type}
- 问题描述: {spec.description}
- 目标函数: {spec.objective}
- 决策变量: {', '.join(spec.variables) if spec.variables else '待确定'}
- 约束条件: {', '.join(spec.constraints) if spec.constraints else '待确定'}
- 已知数据: {', '.join(spec.given_data) if spec.given_data else '待确定'}
- 求解要求: {', '.join(spec.requirements) if spec.requirements else '待确定'}"""

        return [
            Message(role="system", content=STRATEGY_SYSTEM_PROMPT),
            Message(role="user", content=user_content),
        ]

    def parse_response(self, raw: str) -> dict:
        """解析 LLM 响应为结构化数据"""
        json_str = self._extract_json(raw)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # JSON 解析失败，返回基础结构
            return {
                "problem_type": "其他",
                "problem_summary": "LLM 响应解析失败",
                "approaches": [],
                "best_approach": "",
                "recommendation_reason": "JSON 解析失败，请重试",
                "raw_response": raw,
            }

        # 验证必要字段
        required_fields = ["approaches", "best_approach"]
        for field_name in required_fields:
            if field_name not in data:
                data[field_name] = [] if field_name == "approaches" else ""

        return data

    def _extract_json(self, text: str) -> str:
        """从 LLM 响应中提取 JSON"""
        # 尝试提取 ```json ... ``` 代码块
        pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 尝试提取 { ... } JSON 对象
        pattern = r"\{.*\}"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(0).strip()

        return text.strip()

    def to_markdown(self, plan: dict) -> str:
        """将方案转换为 Markdown 格式"""
        lines = []
        lines.append(f"# 建模方案推荐\n")
        lines.append(f"**题目类型**: {plan.get('problem_type', '未知')}\n")
        lines.append(f"**问题概括**: {plan.get('problem_summary', '')}\n")
        lines.append(f"**推荐方案**: {plan.get('best_approach', '')}\n")
        lines.append(f"**推荐理由**: {plan.get('recommendation_reason', '')}\n")
        lines.append("---\n")

        for i, approach in enumerate(plan.get("approaches", []), 1):
            flag = " **[推荐]**" if approach.get("recommended") else ""
            lines.append(f"## 方案 {i}: {approach.get('name', '')}{flag}\n")
            lines.append(f"**原理**: {approach.get('principle', '')}\n")
            lines.append(f"**复杂度**: {approach.get('complexity', '')} | "
                        f"**比赛适用性**: {approach.get('competition_suitability', '')}\n")
            lines.append(f"\n**优点**:")
            for p in approach.get("pros", []):
                lines.append(f"- {p}")
            lines.append(f"\n**缺点**:")
            for c in approach.get("cons", []):
                lines.append(f"- {c}")
            tools = approach.get("required_tools", [])
            if tools:
                lines.append(f"\n**所需工具**: {', '.join(tools)}")
            lines.append("")

        return "\n".join(lines)
