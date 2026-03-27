# Cosmetics Agent 技术清单

这份文档把当前项目中的 agent 技术整理成一张学习地图，分成两类：

1. 已经实现的 agent 技术
2. 还没实现、但很适合后续继续加的 agent 技术

每项都会说明：

- 它是什么
- 它解决什么问题
- 当前状态
- 重点看哪些代码
- 学习时应该关注什么

建议和 [`learning.md`](/Users/jieruiliu/Cosmetics-Agent/learning.md) 一起看。

---

## 0. 当前推荐的 Skill 设计

这部分是“推荐设计”，不是已经接入运行时的 skills 系统。你可以把它理解成：

- 当前 agent = 角色
- 当前推荐的 skill = 每个角色最值得沉淀的一份能力手册

### 当前 8 个 Agent 的一人一 Skill 建议

| Agent | 推荐 Skill | 这个 Skill 主要解决什么 | 重点看哪些代码 |
| --- | --- | --- | --- |
| `RequestPlannerAgent` | `request-planning` | 在执行前生成清晰计划，定义步骤顺序和目标 | `src/cosmetics_agent/multi_agent.py` |
| `TaskCoordinator` | `task-decomposition-and-handoff` | 把用户请求拆成子任务，定义交接顺序和停止条件 | `src/cosmetics_agent/multi_agent.py`, `src/cosmetics_agent/agent.py` |
| `ProfileAnalysisAgent` | `skin-profile-analysis` | 稳定分析肤质、当前状态、长期特征和记忆融合方式 | `src/cosmetics_agent/multi_agent.py`, `src/cosmetics_agent/parser.py`, `src/cosmetics_agent/memory.py` |
| `NeedAnalysisAgent` | `need-clarification` | 识别核心诉求、信息缺口和最小必要追问 | `src/cosmetics_agent/multi_agent.py`, `src/cosmetics_agent/parser.py` |
| `ProductSelectionAgent` | `product-matching-and-ranking` | 统一产品匹配、排序优先级和 RAG 证据使用方法 | `src/cosmetics_agent/multi_agent.py`, `src/cosmetics_agent/recommender.py`, `src/cosmetics_agent/rag.py` |
| `PurchaseLinkAgent` | `shopping-link-collection` | 规范查链接、选链接、回退策略和平台优先级 | `src/cosmetics_agent/multi_agent.py`, `src/cosmetics_agent/research.py`, `src/cosmetics_agent/toolbox.py` |
| `SafetyReviewerAgent` | `ingredient-safety-review` | 统一做禁忌成分、敏感场景和风险提示复核 | `src/cosmetics_agent/multi_agent.py`, `src/cosmetics_agent/guardrails.py` |
| `ReflectionAgent` | `final-constraint-self-check` | 在最终输出前统一检查预算、禁忌、缺失信息和整体一致性 | `src/cosmetics_agent/multi_agent.py`, `src/cosmetics_agent/formatter.py` |

### 如果你只先做 1 个 Skill，我最推荐哪个

最推荐先做：

- `product-matching-and-ranking`

原因：

- 它最贴近当前系统的核心价值
- 它能把推荐规则、RAG 证据和排序方法沉淀下来
- 做完之后你最容易感受到“skill 让 agent 更稳定”这件事

---

## 一、已经实现的 Agent 技术

### 1. 多阶段 Agent Pipeline

### 它是什么

把一次用户请求拆成多个阶段，而不是单次 prompt 直接生成答案。

### 它解决什么问题

- 让系统更稳定
- 让不同能力分层
- 更容易插入 RAG、记忆、工具、ReAct

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/agent.py`
- `src/cosmetics_agent/models.py`

### 学习时重点关注什么

- `run()` 的执行顺序
- 为什么先解析、再记忆、再 RAG、再推荐、再工具

---

### 2. 多 Agent 架构

### 它是什么

把系统拆成多个显式角色 agent 协作，而不是让单个 agent 包揽全部逻辑。

### 它解决什么问题

- 分工更清晰
- trace 更容易解释
- 后续更容易做独立评估

### 当前状态

已实现

### 当前角色

- `RequestPlannerAgent`
- `TaskCoordinator`
- `ProfileAnalysisAgent`
- `NeedAnalysisAgent`
- `ProductSelectionAgent`
- `PurchaseLinkAgent`
- `SafetyReviewerAgent`
- `ReflectionAgent`

### 重点看哪些代码

- `src/cosmetics_agent/multi_agent.py`
- `src/cosmetics_agent/agent.py`
- `src/cosmetics_agent/formatter.py`

### 学习时重点关注什么

- coordinator 和 worker 的分工
- 每个 agent 的输入输出
- 为什么 `SafetyReviewerAgent` 值得独立出来
- 哪个角色最适合抽出独立 skill

---

### 3. Planner / Task Planning

### 它是什么

在真正执行前，先生成一个清晰的任务计划。

### 它解决什么问题

- 让执行顺序更清晰
- 提高复杂流程的可解释性
- 让系统显式回答“接下来该做什么”

### 当前状态

已实现，第一版 planner

### 重点看哪些代码

- `src/cosmetics_agent/multi_agent.py`
- `src/cosmetics_agent/models.py`
- `src/cosmetics_agent/formatter.py`

### 学习时重点关注什么

- planner 和 coordinator 的区别
- planner 输出为什么适合单独展示给用户

---

### 4. 用户画像解析 / Slot Filling

### 它是什么

从自然语言中抽取结构化槽位。

### 它解决什么问题

- 把模糊 query 变成可计算状态
- 为后续推荐和检索提供标准化输入

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/parser.py`
- `src/cosmetics_agent/models.py`

### 学习时重点关注什么

- 关键词匹配到结构化字段的过程
- 澄清问题是怎么生成的

---

### 5. Clarification / 主动追问

### 它是什么

当关键信息缺失时，先问关键问题，而不是盲目给答案。

### 它解决什么问题

- 降低乱推荐
- 提高推荐质量

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/parser.py`

### 学习时重点关注什么

- 哪些字段被定义成“关键缺失信息”
- 追问逻辑为什么放在解析层附近

---

### 6. RAG

### 它是什么

检索增强生成，这个项目里更准确地说是“检索增强推荐决策”。

### 它解决什么问题

- 增强知识依据
- 提升解释性
- 降低只靠规则的僵硬感

### 当前状态

已实现，本地轻量 RAG

### 重点看哪些代码

- `src/cosmetics_agent/rag.py`
- `data/knowledge_base.jsonl`
- `src/cosmetics_agent/recommender.py`

### 学习时重点关注什么

- query terms 怎么构造
- chunk 怎么打分
- 知识证据怎么挂到推荐结果上

---

### 7. 推荐检索与排序

### 它是什么

基于产品库先召回，再做规则打分排序。

### 它解决什么问题

- 给推荐一个稳定底盘
- 减少纯生成式幻觉

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/catalog.py`
- `src/cosmetics_agent/recommender.py`

### 学习时重点关注什么

- 分数是如何构成的
- RAG 和规则是如何混合的

---

### 8. LLM 增强画像

### 它是什么

让 LLM 在规则解析之后，对用户画像做补全与修正。

### 它解决什么问题

- 识别隐含偏好
- 提升解析灵活性

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/llm.py`
- `src/cosmetics_agent/agent.py`
- `src/cosmetics_agent/multi_agent.py`

### 学习时重点关注什么

- 为什么 LLM 放在“增强层”而不是替代规则解析

---

### 9. LLM 复核排序

### 它是什么

先用规则做初排，再用 LLM 做复核。

### 它解决什么问题

- 提升最终排序的语义合理性
- 让解释更自然

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/llm.py`
- `src/cosmetics_agent/multi_agent.py`

### 学习时重点关注什么

- 为什么用“双层决策”而不是让 LLM 直接排序

---

### 10. Tool Calling

### 它是什么

让 agent 调用外部工具，而不是只在上下文里“想”。

### 它解决什么问题

- 能联网
- 能找购买链接
- 能读网页摘要

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/toolbox.py`
- `src/cosmetics_agent/research.py`

### 学习时重点关注什么

- 工具 schema 设计
- 工具结果如何回填到推荐结果
- 为什么 `PurchaseLinkAgent` 很适合挂 `shopping-link-collection` skill

---

### 11. ReAct

### 它是什么

`Thought -> Action -> Observation -> Thought`

### 它解决什么问题

- 让工具调用更像智能体决策
- 让中间决策过程可观察

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/research.py`
- `src/cosmetics_agent/llm.py`
- `src/cosmetics_agent/models.py`

### 学习时重点关注什么

- 启发式 ReAct 和 LLM 驱动 ReAct 的区别
- 为什么要把轨迹显式输出

---

### 12. 短期记忆

### 它是什么

服务当前 session 的 working memory。

### 它解决什么问题

- 多轮对话连续性
- 避免用户每轮重复说同样信息

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/memory.py`
- `src/cosmetics_agent/cli.py`

### 学习时重点关注什么

- recent K messages
- 超长压缩摘要
- session_id 的作用

---

### 13. 长期记忆

### 它是什么

服务跨会话个性化的 profile memory。

### 它解决什么问题

- 记住稳定偏好
- 让系统越用越懂用户

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/memory.py`

### 学习时重点关注什么

- `user_profiles`
- `user_memories`
- 写回策略

---

### 14. Guardrails / Safety Layer

### 它是什么

在输出前做风险提醒和安全边界控制。

### 它解决什么问题

- 减少不合适建议
- 增强可信度

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/guardrails.py`
- `src/cosmetics_agent/multi_agent.py`

### 学习时重点关注什么

- 为什么安全复核单独做一个 agent 很有价值
- 为什么这一层最适合沉淀成 `ingredient-safety-review` skill

---

### 15. Self-check / Reflection

### 它是什么

在最终输出前再做一次统一检查，确认结果与预算、禁忌、缺失信息和整体一致性没有明显冲突。

### 它解决什么问题

- 降低明显错误
- 提升最终答案可信度
- 让 agent 更像“会自己检查”的系统

### 当前状态

已实现，第一版 self-check

### 重点看哪些代码

- `src/cosmetics_agent/multi_agent.py`
- `src/cosmetics_agent/formatter.py`
- `src/cosmetics_agent/models.py`

### 学习时重点关注什么

- self-check 和 guardrails 的区别
- 为什么 self-check 更偏“最终一致性”，guardrails 更偏“安全边界”

---

### 16. Evaluation Loop

### 它是什么

用固定数据集和固定指标，自动评估当前 agent 在预算、品类、风险提示、追问、RAG、Planner、自检等维度上的表现。

### 它解决什么问题

- 不再只靠人工体感判断“是不是更智能”
- 能做回归测试
- 能比较不同 agent 技术叠加前后的变化

### 当前状态

已实现，第一版离线规则评测

### 重点看哪些代码

- `src/cosmetics_agent/evals.py`
- `data/eval_dataset.jsonl`
- `src/cosmetics_agent/cli.py`

### 学习时重点关注什么

- 为什么第一版 eval 先不用 LLM judge
- 为什么指标要覆盖 planner、self-check、RAG，而不只覆盖最终推荐文本
- 以后怎么把 eval 变成多版本比较工具

---

### 17. Skill-ready 架构设计

### 它是什么

虽然当前项目还没有正式接入运行时 skills 机制，但当前多 agent 结构已经非常适合挂 skill。

### 它解决什么问题

- 为每个 agent 提供稳定方法论
- 减少规则散落在多个文件里
- 方便后面做按角色复用和升级

### 当前状态

已具备架构条件，skill 本身待实现

### 重点看哪些代码

- `src/cosmetics_agent/multi_agent.py`
- `src/cosmetics_agent/research.py`
- `src/cosmetics_agent/recommender.py`
- `src/cosmetics_agent/guardrails.py`

### 学习时重点关注什么

- 哪些逻辑已经足够稳定，值得被提炼成 skill
- 哪些 skill 更像“方法手册”，哪些更像“工具使用规范”

---

### 18. Explainability / Trace Rendering

### 它是什么

把内部状态、工具调用、ReAct、记忆和多 agent 协作过程展示给用户。

### 它解决什么问题

- 帮助调试
- 帮助学习
- 提升系统透明度

### 当前状态

已实现

### 重点看哪些代码

- `src/cosmetics_agent/formatter.py`
- `src/cosmetics_agent/models.py`

### 学习时重点关注什么

- 为什么“可解释”是 agent 系统里非常重要的一层

---

## 二、待实现的 Agent 技术

### 1. Dynamic Planner / Task Decomposition

### 它是什么

比现在的协调器更进一步，不只是固定拆角色，而是根据任务动态拆子任务。

### 它能提升什么

- 复杂需求处理更灵活
- 多 agent 分工更智能

### 适合放在哪

- `multi_agent.py`
- `llm.py`

---

### 2. Episodic Memory

### 它是什么

记录具体经历，而不只是稳定偏好。

### 它能提升什么

- 记住某次踩雷
- 记住某次成功体验

### 适合放在哪

- `memory.py`

---

### 3. 向量化长期记忆

### 它是什么

给长期记忆加 embedding 和语义召回能力。

### 它能提升什么

- 更像语义级“想起以前的事”
- 处理模糊偏好更强

### 适合放在哪

- `memory.py`
- 新增 `memory_retrieval.py`

---

### 4. Tool Result Verification

### 它是什么

对工具返回结果再做一次校验。

### 它能提升什么

- 减少错链
- 提高购买链接可信度

### 适合放在哪

- `research.py`
- `toolbox.py`

---

### 5. LLM-as-a-judge Eval

### 它是什么

在规则指标之外，再让模型对推荐解释质量、完整性和自然度做评审。

### 它能提升什么

- 补上纯规则指标难以衡量的“表达质量”
- 更适合评估复杂多 agent 输出

### 适合放在哪

- `src/cosmetics_agent/evals.py`
- 新增 `eval_prompts.py`

---

### 6. Dynamic Memory Curator

### 它是什么

专门判断“什么值得写入长期记忆”的 agent。

### 它能提升什么

- 降低垃圾记忆
- 提高长期记忆质量

### 适合放在哪

- `multi_agent.py`
- `memory.py`

---

### 7. Runtime Skills System

### 它是什么

让当前推荐的 skills 真正变成可加载、可替换、可复用的能力模块。

### 它能提升什么

- 不同 agent 的行为更稳定
- 更容易持续演化每个角色的方法论
- 更方便做 A/B skill 对比

### 适合放在哪

- 新增 `skills/`
- `multi_agent.py`
- `learning.md`

---

## 三、建议的学习顺序

如果你想按“技术”而不是按“文件”学习，我建议这个顺序：

1. 多阶段 pipeline
2. 用户画像解析
3. 推荐排序
4. RAG
5. 记忆
6. Tool calling
7. ReAct
8. 多 Agent
9. Planner
10. Self-check
11. Evaluation loop
12. Skill-ready 架构
13. Guardrails
14. Explainability
15. Planner 深化版
16. Episodic memory
17. LLM judge eval

---

## 四、建议你现在优先学的 5 个点

如果你想先抓最核心的 agent 技术，优先看：

1. `multi_agent.py`
2. `rag.py`
3. `memory.py`
4. `research.py`
5. `llm.py`

原因是这 5 个文件最能体现：

- 多 agent
- 检索增强
- 记忆
- 工具使用
- ReAct
- LLM 增强

---

## 五、和学习路线图的关系

- 如果你想按“文件顺序”学习：看 [`learning.md`](/Users/jieruiliu/Cosmetics-Agent/learning.md)
- 如果你想按“agent 技术”学习：看这份 `agent_techniques.md`

最好的方式是两份一起看：

- `learning.md` 告诉你先看什么代码
- `agent_techniques.md` 告诉你每段代码对应什么 agent 技术
