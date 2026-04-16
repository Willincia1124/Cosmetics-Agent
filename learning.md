# Cosmetics Agent 学习路线图

这份文档是给“边做边学 agent 技术”的阅读指南。目标不是把所有文件都扫一遍，而是让你按一个合理顺序去理解：

1. 当前这个美妆导购 agent 是怎么工作的
2. 每个模块在整个系统里扮演什么角色
3. 这些模块分别对应了哪些 agent 技术
4. 你看完每一层之后，应该掌握什么

如果你配合 [`README.md`](/Users/jieruiliu/Cosmetics-Agent/README.md) 里的系统架构图和 workflow 图一起看，会更清楚。

---

## 学习顺序总览

推荐按照这个顺序阅读：

1. `src/cosmetics_agent/agent.py`
2. `src/cosmetics_agent/models.py`
3. `src/cosmetics_agent/cli.py`
4. `src/cosmetics_agent/multi_agent.py`
5. `src/cosmetics_agent/parser.py`
6. `src/cosmetics_agent/catalog.py`
7. `src/cosmetics_agent/recommender.py`
8. `src/cosmetics_agent/rag.py`
9. `src/cosmetics_agent/memory.py`
10. `src/cosmetics_agent/toolbox.py`
11. `src/cosmetics_agent/research.py`
12. `src/cosmetics_agent/llm.py`
13. `src/cosmetics_agent/guardrails.py`
14. `src/cosmetics_agent/formatter.py`
15. `src/cosmetics_agent/config.py`
16. `src/cosmetics_agent/evals.py`
17. `data/eval_dataset.jsonl`

这个顺序的原则是：

- 先看“总控”，建立全局脑图
- 再看“状态结构”，理解系统里流动的是什么数据
- 再看“核心业务链路”：解析、检索、推荐
- 再看“增强能力”：多 Agent、记忆、工具、LLM、ReAct
- 最后看“收尾模块”：安全、格式化、配置
- 最后再看“评测模块”：怎么验证这些 agent 技术是否真的带来提升

---

## 第一层：先建立全局脑图

### 1. `src/cosmetics_agent/agent.py`

这是整个系统最重要的文件，也是最推荐你第一个看的文件。

### 这个文件负责什么

- 负责把所有模块串起来
- 决定请求的执行顺序
- 是整个 agent 的 orchestrator

### 重点关注什么

- `BeautyAdvisorAgent.__init__`
- `BeautyAdvisorAgent.run`
- `BeautyAdvisorAgent.render`
- `_build_summary`

### 你应该重点看什么逻辑

`run()` 里基本就是当前系统的主流程：

1. 解析 query
2. 合并记忆
3. 运行 RAG
4. 如有 LLM，先增强画像
5. 推荐候选商品
6. 如有 LLM，复核排序
7. 如开启 live tools，进入 research / ReAct
8. 组装 `AgentResponse`
9. 写回记忆

### 这个文件对应的 agent 技术

- 多阶段 agent pipeline
- orchestration / workflow control
- 模块编排

### 看完你应该理解什么

- 这个项目不是单次 prompt，而是一个编排好的 agent 系统
- 整个请求处理链条长什么样
- 各模块是怎么串起来的

---

## 第二层：理解系统里的核心数据结构

### 2. `src/cosmetics_agent/models.py`

这个文件定义了整个系统里最关键的数据结构。

### 这个文件负责什么

- 定义产品结构
- 定义用户画像结构
- 定义推荐结果结构
- 定义工具输出结构
- 定义 ReAct 轨迹结构

### 重点关注什么

- `UserProfile`
- `Product`
- `Recommendation`
- `KnowledgeChunk`
- `AgentResponse`
- `ToolEvent`
- `ReActStep`

### 为什么它很重要

你要理解 agent，首先要知道“它到底在处理什么状态”。  
当前系统的 agent 不是直接处理原始自然语言，而是一直在处理这些结构化对象。

### 这个文件对应的 agent 技术

- state modeling
- structured agent state
- typed intermediate representations

### 看完你应该理解什么

- query 被解析后会变成什么
- 推荐结果内部有哪些字段
- 工具调用结果是如何被记录的
- ReAct 轨迹是如何表示的

---

## 第三层：先看入口，知道怎么触发系统

### 3. `src/cosmetics_agent/cli.py`

### 这个文件负责什么

- CLI 命令入口
- `chat`、`repl`、`kb`、`memory` 命令

### 重点关注什么

- `build_parser`
- `run_chat`
- `run_repl`
- `run_kb`
- `run_memory`

### 为什么值得看

这个文件会告诉你：  
当前项目不是 Web app，而是一个本地 CLI agent。  
同时它也是你今后测试各模块最直接的入口。

### 这个文件对应的 agent 技术

- agent interface / user interface
- local testing loop

### 看完你应该理解什么

- 怎么触发短期记忆和长期记忆
- 怎么单独调试 RAG
- 怎么单独查看持久化记忆

---

## 第四层：理解“用户话语 -> 结构化画像”

### 4. `src/cosmetics_agent/multi_agent.py`

这是当前“多 Agent 架构”的核心文件，也是你学习多智能体最值得重点看的地方。

### 这个文件负责什么

- 显式定义多个角色 agent
- 定义各角色之间的协作边界
- 由协调器把这些角色串起来

### 重点关注什么

- `RequestPlannerAgent`
- `TaskCoordinatorAgent`
- `ProfileAnalysisAgent`
- `NeedAnalysisAgent`
- `ProductSelectionAgent`
- `PurchaseLinkAgent`
- `SafetyReviewerAgent`
- `ReflectionAgent`
- `MultiAgentBeautyAdvisor.run`

### 推荐你重点理解的几个问题

- 为什么不是把所有逻辑继续塞进 `agent.py`
- 每个角色的输入和输出分别是什么
- 哪些角色更偏“分析”，哪些更偏“行动”
- `SafetyReviewerAgent` 为什么单独拆出来
- `RequestPlannerAgent` 和 `TaskCoordinatorAgent` 的区别是什么
- `ReflectionAgent` 和 `SafetyReviewerAgent` 的区别是什么

### 这个文件对应的 agent 技术

- multi-agent architecture
- coordinator-worker pattern
- role-specialized agents
- explicit responsibility boundaries

### 看完你应该理解什么

- 多 agent 不是“多模型一起跑”那么简单，而是任务分工更清晰
- 你这个项目里每个 agent 分别负责哪一类工作
- 多 agent 的价值更多体现在结构化协作和更清晰的 trace
- planner 决定“先做什么”
- self-check 决定“最后结果是否站得住”

### 当前最推荐的一人一 Skill 设计

这一组 skill 目前还没有作为独立运行时 skill 文件接入，但非常适合你后续继续扩展：

- `RequestPlannerAgent` -> `request-planning`
- `TaskCoordinator` -> `task-decomposition-and-handoff`
- `ProfileAnalysisAgent` -> `skin-profile-analysis`
- `NeedAnalysisAgent` -> `need-clarification`
- `ProductSelectionAgent` -> `product-matching-and-ranking`
- `PurchaseLinkAgent` -> `shopping-link-collection`
- `SafetyReviewerAgent` -> `ingredient-safety-review`
- `ReflectionAgent` -> `final-constraint-self-check`

学习这些 skill 时，建议你分别观察：

- 这个 agent 现在的输入输出是什么
- 哪部分逻辑已经稳定到值得抽成 skill
- 哪部分规则未来不应该继续散落在主流程里

如果你要先挑最有学习价值的一个 skill 来做，我最推荐：

- `ProductSelectionAgent` 的 `product-matching-and-ranking`

因为它最能体现“领域知识 + 排序策略 + RAG 使用方式”如何沉淀成可复用能力。

---

## 第五层：理解“用户话语 -> 结构化画像”

### 5. `src/cosmetics_agent/parser.py`

### 这个文件负责什么

- 把中文自然语言 query 解析成 `UserProfile`
- 检测缺失信息并生成澄清问题

### 重点关注什么

- `parse_user_query`
- `build_clarifying_questions`

### 推荐你边看边想的问题

- 当前支持哪些肤质关键词
- 预算是怎么抽取的
- 成分偏好和禁忌是怎么识别的
- 系统什么时候会追问用户

### 这个文件对应的 agent 技术

- slot filling
- user profiling
- clarification behavior

### 看完你应该理解什么

- agent 是如何把“模糊语言”变成“结构化决策输入”的
- 为什么说解析层是后面所有智能行为的基础

---

## 第六层：看底层数据源

### 6. `src/cosmetics_agent/catalog.py`

### 这个文件负责什么

- 提供当前内置产品种子数据

### 建议关注什么

- 每个产品的字段设计
- 产品数据是如何支撑推荐逻辑的

### 为什么值得看

这个文件会帮助你理解：

- 推荐引擎到底依赖哪些商品信息
- 当前推荐为什么是“基于产品库”而不是纯生成

### 对应的 agent 技术

- knowledge grounding
- structured product memory

### 看完你应该理解什么

- 产品库是 agent 的候选空间
- 为什么本地库是推荐系统的“落脚点”

---

## 第七层：理解推荐引擎本身

### 7. `src/cosmetics_agent/recommender.py`

### 这个文件负责什么

- 检索候选商品
- 给候选商品打分
- 生成推荐结果

### 重点关注什么

- `retrieve_candidates`
- `score_product`
- `recommend_products`

### 推荐重点理解的维度

- 预算如何影响分数
- 肤质如何影响分数
- 功效如何影响分数
- 成分偏好 / 禁忌如何影响分数
- RAG 证据如何影响分数

### 对应的 agent 技术

- retrieval + ranking
- decision scoring
- explainable recommendation

### 看完你应该理解什么

- 现在的推荐结果主要是怎么排出来的
- 为什么这是系统的“稳定底盘”

---

## 第八层：理解 RAG

### 8. `src/cosmetics_agent/rag.py`

### 这个文件负责什么

- 从本地知识库中检索知识片段
- 给知识片段打分
- 给具体推荐商品绑定证据

### 重点关注什么

- `load_knowledge_base`
- `retrieve_knowledge`
- `evidence_for_product`
- `score_chunk`

### 推荐边看边思考

- query term 是怎么构造的
- 为什么有 `_chunk_allowed_for_profile`
- 为什么要做 `evidence_for_product`

### 对应的 agent 技术

- RAG
- retrieval-augmented reasoning
- external knowledge grounding

### 看完你应该理解什么

- RAG 在这个项目里不是“直接回答”，而是“增强推荐决策”
- 为什么说 RAG 让系统更可解释、更易扩展

---

## 第九层：理解记忆系统

### 9. `src/cosmetics_agent/memory.py`

### 这个文件负责什么

- 短期记忆持久化
- 长期记忆持久化
- 最近消息保留 + 超长压缩
- 稳定画像和偏好沉淀

### 重点关注什么

- `MemoryStore`
- `SessionMemory`
- `remember_turn`
- `_compress_messages`
- `_persist_long_term_memory`

### 建议重点看哪些概念

- `session_state`
- `session_messages`
- `user_profiles`
- `user_memories`

### 对应的 agent 技术

- short-term memory
- long-term memory
- memory compression
- profile memory

### 看完你应该理解什么

- 为什么短期记忆用 recent K + summary
- 为什么长期记忆先存结构化 profile 和 preference items
- 记忆是如何写回系统的

---

## 第十层：理解工具本身

### 10. `src/cosmetics_agent/toolbox.py`

### 这个文件负责什么

- 定义工具接口
- 提供联网能力
- 执行网页搜索、商品页查找、摘要提取、购买链接获取

### 重点关注什么

- `tool_schemas`
- `call`
- `search_web`
- `search_products`
- `extract_product_info`
- `get_purchase_links`

### 对应的 agent 技术

- tool calling
- function schema design
- external action layer

### 看完你应该理解什么

- 为什么工具层要和 agent orchestration 分开
- 工具的输入输出为什么要结构化

---

## 第十一层：理解工具编排和 ReAct

### 11. `src/cosmetics_agent/research.py`

### 这个文件负责什么

- 决定何时调用 live tools
- 把工具结果挂回推荐结果
- 记录 ToolEvent
- 记录 ReAct 轨迹

### 重点关注什么

- `ResearchOrchestrator.enrich_recommendations`
- `_try_llm_tool_calling`

### 看这个文件时你要特别注意

这里是“工具存在”到“智能体真的会用工具”之间的关键桥梁。

### 对应的 agent 技术

- tool orchestration
- ReAct
- action-observation loop

### 看完你应该理解什么

- 工具不是自己会工作的，必须有编排器
- ReAct 轨迹是如何生成并挂到最终结果里的

---

## 第十二层：理解 LLM 在系统里扮演什么角色

### 12. `src/cosmetics_agent/llm.py`

### 这个文件负责什么

- 和 OpenAI-compatible API 通信
- 用 LLM 做画像增强
- 用 LLM 做候选复核
- 用 LLM 做 ReAct 决策

### 重点关注什么

- `enhance_profile`
- `rerank_and_explain`
- `run_react_tool_loop`
- `_chat_json`
- `_chat_raw`

### 推荐边看边想的问题

- 为什么 LLM 不直接负责整个推荐
- 为什么它更适合放在“增强”和“复核”位置
- 为什么 ReAct 里会用 JSON 结构返回决策

### 对应的 agent 技术

- LLM reasoning module
- LLM-as-planner
- structured LLM control
- model-guided ReAct

### 看完你应该理解什么

- 这个项目里 LLM 是怎么嵌入 agent pipeline 的
- 为什么说“LLM 不是全部，只是一个模块”

---

## 第十三层：理解安全边界

### 13. `src/cosmetics_agent/guardrails.py`

### 这个文件负责什么

- 给高风险情况增加提醒
- 给敏感肌/痘肌增加保守提示

### 重点关注什么

- `build_global_cautions`

### 对应的 agent 技术

- guardrails
- safety layer
- constrained output

### 看完你应该理解什么

- agent 为什么不能只追求“聪明”，还要有边界

---

## 第十四层：理解最终输出怎么组织

### 14. `src/cosmetics_agent/formatter.py`

### 这个文件负责什么

- 把 `AgentResponse` 变成用户终端里看到的文本

### 重点关注什么

- `format_profile`
- `format_recommendation`
- `format_agent_response`

### 为什么值得看

你现在看到的这些“可解释痕迹”：

- 用户画像
- 知识依据
- Tool Calling 记录
- ReAct 轨迹
- 短期记忆摘要
- 长期记忆片段

基本都在这里被组织出来。

### 对应的 agent 技术

- explainability
- trace rendering
- user-facing transparency

### 看完你应该理解什么

- 为什么一个好的 agent 不只是做决策，还要能把决策解释清楚

---

## 第十五层：最后看配置

### 15. `src/cosmetics_agent/config.py`

### 这个文件负责什么

- 读取 LLM 配置
- 读取 Tool 配置

### 重点关注什么

- `LLMConfig.from_env`
- `ToolConfig.from_env`

### 对应的 agent 技术

- environment-driven capability switching
- runtime feature flags

### 看完你应该理解什么

- 为什么同一个 agent 可以在不同运行模式间切换
- 为什么“没配 API key 时自动回退”是一个重要工程能力

---

## 推荐的实际学习节奏

如果你想边读边实践，我推荐用这个节奏：

### 第一轮：建立整体理解

读：

1. `agent.py`
2. `models.py`
3. `cli.py`

目标：

- 看懂整体流程
- 知道系统入口和输出结构

### 第二轮：看核心推荐链路

读：

1. `parser.py`
2. `catalog.py`
3. `recommender.py`
4. `rag.py`

目标：

- 看懂没有 LLM 时系统也能工作的原因
- 理解推荐引擎的底层逻辑

### 第三轮：看多 Agent 和智能增强能力

读：

1. `multi_agent.py`
2. `memory.py`
3. `toolbox.py`
4. `research.py`
5. `llm.py`

目标：

- 理解多 Agent、记忆、工具、LLM、ReAct 是怎么叠加上去的

### 第四轮：看边界与体验

读：

1. `guardrails.py`
2. `formatter.py`
3. `config.py`

目标：

- 理解安全、配置和用户体验层

---

## 建议你边学边跑的命令

### 1. 跑基础推荐

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli chat --query "我是混油痘肌，预算300，想找清爽不闷痘的防晒"
```

### 2. 单独看 RAG

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli kb --query "混油皮通勤底妆，预算300，想要雾面持妆"
```

### 3. 跑短期记忆

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli repl --session-id demo-session --user-id demo-user --message-window 4
```

### 4. 看持久化记忆

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli memory --session-id demo-session --user-id demo-user --message-window 4
```

### 5. 跑 live tools + ReAct

```bash
export LIVE_TOOLS_ENABLED=1
PYTHONPATH=src python3 -m cosmetics_agent.cli chat --query "混油皮，想找通勤底妆，预算300"
```

### 6. 跑 LLM 增强链路

```bash
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY=你的_key
export LLM_MODEL=openrouter/free
PYTHONPATH=src python3 -m cosmetics_agent.cli chat --query "我是混油痘肌，预算300，想找清爽不闷痘的防晒"
```

### 7. 跑离线 eval

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli eval
```

### 8. 只跑单个 eval case

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli eval --case-id sunscreen_oily_budget
```

---

## 你学习时最值得观察的几个问题

1. 哪些地方是“规则驱动”的，哪些地方是“LLM 驱动”的？
2. 哪些地方在处理结构化状态，哪些地方在处理自然语言？
3. 单 Agent 主编排和多 Agent 分工有什么区别？
4. RAG 是怎么影响推荐排序的？
5. 记忆是怎么被读取、合并、写回的？
6. Tool calling 是怎么从“工具存在”变成“agent 会用工具”的？
7. ReAct 和普通 tool calling 的区别是什么？
8. guardrails 是在流程的哪个位置生效的？
9. eval 为什么要尽量做成固定数据集 + 固定指标，而不是只靠人工体感？
10. planner、自检、RAG 这些能力，分别该怎么被评估？

---

## 看完这一轮后，你应该掌握什么

如果你把这份路线走完，你应该能清楚回答：

- 这个 agent 的主流程是什么
- 当前系统用了哪些 agent 技术
- 每种 agent 技术落在了哪些代码文件里
- 哪些模块属于“稳定底盘”，哪些模块属于“智能增强”
- 如果你下一步要继续加 Vector Memory、Tool Verification、Skill Runtime，应该改哪些地方
- 以后怎么判断一个新 agent 技术是真的带来了提升

---

## 最后补一层：评估这些 Agent 技术是否有效

### 16. `src/cosmetics_agent/evals.py`

### 这个文件负责什么

- 加载评测数据集
- 跑固定测试 case
- 用规则指标评估当前 agent 输出
- 生成可读的评测报告

### 重点关注什么

- `EvalCase`
- `MetricResult`
- `evaluate_case`
- `run_evals`
- `format_eval_run`

### 这个文件对应的 agent 技术

- evaluation loop
- regression benchmarking
- agent capability measurement

### 看完你应该理解什么

- 为什么评测不能只靠“感觉更像人”
- 为什么第一版 eval 很适合先做规则型指标
- 后面如果你加多 agent、skills、tool verification，要怎么继续扩展评测

### 17. `data/eval_dataset.jsonl`

### 这个文件负责什么

- 定义固定测试集合
- 把“好结果应该长什么样”变成可机器检查的约束

### 重点关注什么

- `expected_categories`
- `budget_max`
- `avoided_ingredients`
- `require_clarification`
- `require_safety_note`
- `require_plan`
- `require_self_check`

### 看完你应该理解什么

- 为什么 eval dataset 本质上是在定义“能力边界”
- 为什么未来做多 agent 对比时，应该先扩这个文件，再改模型逻辑

---

## 高并发场景下，Agent 如何保证稳定性和时效性

这一节不是当前仓库已经全部实现的功能，而是你后面如果想把这个项目从“本地可跑的 agent”继续往“线上可承载并发请求的服务”演进时，最值得系统学习的一组技术。

你可以把目标拆成两件事：

1. 稳定性：不要轻易崩，不要级联故障，不要把下游拖死
2. 时效性：响应尽量快，超时时能优雅降级，而不是一直卡住

---

### 1. 超时控制与 Deadline 传播

### 它是什么

给整条请求链路设总超时，再给每个子阶段设局部超时。

### 它为什么重要

agent 往往不是一次函数调用，而是一条长链路：

- 解析
- 检索
- LLM 调用
- 工具调用
- 自检

如果没有 deadline，某一个慢环节就会把整条请求拖住。

### 在这个项目里怎么理解

当前最适合先加超时控制的地方是：

- `llm.py`
- `research.py`
- `toolbox.py`

比较合理的做法是：

- 整个请求最多允许执行 N 秒
- 工具调用单次最多 M 秒
- LLM 调用超过阈值就降级到规则模式

### 它提升什么

- 防止单请求无限挂起
- 提高尾延迟表现
- 让系统更容易做 SLA 管理

---

### 2. 降级策略与 Fallback

### 它是什么

当高成本或高风险模块不可用时，自动回退到低成本、可用性更高的版本。

### 它为什么重要

高并发时最容易出问题的通常是：

- LLM 限流
- 外部搜索不稳定
- 电商链接抓取超时

如果没有 fallback，请求就直接失败了。

### 在这个项目里怎么理解

你这个项目天生就很适合做分层降级：

- 第一层：规则解析 + 本地产品库 + 本地 RAG
- 第二层：加 LLM 增强画像和 rerank
- 第三层：加 live tools 和购买链接

也就是说，高峰期完全可以按优先级关闭：

1. 先关 live tools
2. 再关 LLM rerank
3. 保留最核心的规则推荐底盘

### 它提升什么

- 高峰期服务可用性更强
- 避免因为最贵模块异常导致整体不可用
- 让“能返回一个可接受结果”优先于“必须返回最强结果”

---

### 3. 并行化与阶段拆分

### 它是什么

把彼此独立的步骤并行执行，而不是全部串行。

### 它为什么重要

agent 请求很多时候慢，不是因为单个动作特别慢，而是因为串行阶段太多。

### 在这个项目里哪些东西适合并行

- 多个商品的购买链接收集
- 多个网页信息提取
- RAG 检索和部分画像补充前置计算
- 多个候选商品的工具增强

比如当前 `PurchaseLinkAgent` 如果后面要扩展，就很适合把前 2 到 3 个候选商品的联网补充并行化。

### 它提升什么

- 降低总耗时
- 提高吞吐
- 更适合高并发时缩短平均响应时间

### 学习时要注意什么

并行化不是越多越好，还要配合：

- 限流
- 并发池
- 超时控制

否则会把外部依赖直接打爆。

---

### 4. 限流、舱壁隔离和并发配额

### 它是什么

给不同类型的资源设置并发上限，避免互相拖垮。

### 它为什么重要

agent 系统的资源消耗很不均匀：

- LLM 调用贵
- 外部搜索慢
- 本地规则计算便宜

如果所有请求都无上限打到 LLM 或工具层，很容易雪崩。

### 在这个项目里怎么理解

可以把资源池拆开：

- 规则/RAG 层一个池
- LLM 层一个池
- live tools 层一个池

即使工具层被打满，规则推荐也应该还能继续服务。

### 它提升什么

- 防止级联故障
- 保护关键路径
- 让便宜能力不被昂贵能力拖死

---

### 5. 缓存

### 它是什么

把高重复、可复用的结果缓存起来，避免重复计算和重复调用下游。

### 它为什么重要

高并发场景里，重复请求很多：

- 类似 query 重复出现
- 热门商品的购买链接反复查
- 同一个知识检索结果多次命中

### 在这个项目里最适合缓存什么

- RAG 检索结果
- 商品购买链接结果
- 网页摘要提取结果
- 相同 query 的 LLM rerank 结果

### 缓存的层次

- 进程内短缓存：最快，适合开发期
- Redis 缓存：更适合服务化部署
- 按 session/user 的轻量状态缓存：减少频繁读库

### 它提升什么

- 降低平均时延
- 降低 LLM 和工具调用成本
- 提高高峰期吞吐

---

### 6. 异步化与后台任务

### 它是什么

把不必须阻塞主响应的步骤挪到后台执行。

### 它为什么重要

不是所有步骤都必须在首屏结果返回前完成。

### 在这个项目里哪些步骤可以异步

- 更完整的购买链接补充
- 更深的网页抽取
- 长期记忆整理
- 离线评测和埋点分析

一种很实用的思路是：

- 首先返回核心推荐
- 再异步补充更完整的购买链接或解释

### 它提升什么

- 显著缩短首响应时间
- 让重任务不会阻塞主链路
- 更适合面向真实用户的体验优化

---

### 7. 结果流式返回

### 它是什么

不是等所有步骤都完成后再一次性返回，而是边执行边逐步返回结果。

### 它为什么重要

在用户感知里，“先看到进展”往往比“最后总耗时少 1 秒”更重要。

### 在 agent 里常见的流式内容

- 当前正在分析用户画像
- 当前正在检索知识库
- 当前正在补充购买链接
- 主推荐先返回，补充信息后续追加

### 在这个项目里怎么理解

如果后面从 CLI 升级成 Web/API 服务，planner、多 agent step、tool event、react step 都天然适合变成流式事件。

### 它提升什么

- 提高用户体感速度
- 降低“系统卡住了”的感觉
- 更适合复杂 agent workflow

---

### 8. 幂等、重试和断路器

### 它是什么

- 幂等：重复执行不会产生错误副作用
- 重试：临时失败时自动再试
- 断路器：下游坏了时先快速失败，不再继续打爆它

### 它为什么重要

高并发下的失败很多不是永久错误，而是瞬时错误。

### 在这个项目里怎么理解

最适合做这些保护的地方是：

- 外部 LLM 调用
- 搜索工具调用
- 商品页抓取

但要注意：

- 不是所有失败都该重试
- 超时和 5xx 可以重试
- 参数错误和鉴权错误通常不该重试

### 它提升什么

- 降低偶发失败率
- 避免雪崩扩散
- 提高系统韧性

---

### 9. 请求去重与合并

### 它是什么

当大量相同请求同时到来时，只真的执行一次，其他请求复用结果。

### 它为什么重要

高峰期很可能出现热点请求，比如：

- 同一种肤质和预算的热门防晒推荐
- 同一个商品链接被大量查询

### 在这个项目里适合怎么做

- 对相同 query + 配置生成 cache key
- 正在处理中的请求做 in-flight dedup
- 后来的同 key 请求直接等待前一个结果

### 它提升什么

- 大幅减少重复 LLM 调用
- 降低工具压力
- 提高热点场景吞吐

---

### 10. 可观测性：日志、指标、链路追踪

### 它是什么

把 agent 每个阶段的耗时、成功率、失败原因记录下来。

### 它为什么重要

没有观测，就不知道慢在哪里，也不知道高并发时到底是哪层先崩。

### 在 agent 系统里最该看的指标

- 总请求耗时
- 各阶段耗时
- LLM 成功率 / 超时率
- tool calling 成功率 / 超时率
- fallback 触发率
- cache hit rate
- 每阶段并发占用

### 在这个项目里怎么理解

你现在已经有：

- planner steps
- multi-agent steps
- tool events
- react steps
- self-check notes

这些其实已经是很好的“结构化 trace 底盘”。后面只要再加：

- 时间戳
- request_id
- session_id
- error code

就能逐步演进成线上可观测体系。

### 它提升什么

- 更快定位瓶颈
- 更快定位故障
- 为后续优化提供数据基础

---

### 11. 评测和流量分层

### 它是什么

不要把所有新 agent 技术直接全量上线，而是分层实验和评估。

### 它为什么重要

多 agent、planner、self-check、tool calling 都可能让效果更好，但也可能让时延更高。

### 适合怎么做

- 一部分流量走纯规则底盘
- 一部分流量走 LLM 增强
- 一部分流量走多 agent 全链路

然后比较：

- 响应时间
- 错误率
- 购买链接命中率
- eval 分数

### 它提升什么

- 避免一次性全量上线高风险架构
- 更科学地比较“更智能”和“更慢”之间的平衡
- 帮你判断某个 agent 技术是否值得保留

---

## 如果把这些技术映射到你这个项目，最推荐的落地顺序

如果你后面真想把这个项目往服务化推进，我最建议按这个顺序学和做：

1. 超时控制 + fallback
2. 缓存
3. 限流和并发配额
4. 并行化购买链接和网页增强
5. 可观测性
6. 异步化非关键路径任务
7. 流式输出
8. A/B eval 和流量分层

这个顺序的原因是：

- 前四项最直接影响稳定性和时延
- 第五项决定你有没有能力继续调优
- 后三项更偏产品体验和系统演进

---

## 建议的下一步学习方向

等你把当前代码读顺之后，最推荐继续学这几个方向：

1. Episodic memory
2. 向量化长期记忆
3. Tool result verification
4. Runtime skills system
5. LLM-as-a-judge eval
6. A/B eval and regression dashboard

另外建议配合阅读：

- [`agent_techniques.md`](/Users/jieruiliu/Cosmetics-Agent/agent_techniques.md)

这份文档会把“已经实现”和“待实现”的 agent 技术整理成一份完整清单，并标清每种技术该看哪些代码。

如果你愿意，后面我还可以继续给你补一份：

`learning_advanced.md`

专门讲“接下来每一种 agent 技术应该怎么继续往这个项目里加”。
