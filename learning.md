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
4. `src/cosmetics_agent/parser.py`
5. `src/cosmetics_agent/catalog.py`
6. `src/cosmetics_agent/recommender.py`
7. `src/cosmetics_agent/rag.py`
8. `src/cosmetics_agent/memory.py`
9. `src/cosmetics_agent/toolbox.py`
10. `src/cosmetics_agent/research.py`
11. `src/cosmetics_agent/llm.py`
12. `src/cosmetics_agent/guardrails.py`
13. `src/cosmetics_agent/formatter.py`
14. `src/cosmetics_agent/config.py`

这个顺序的原则是：

- 先看“总控”，建立全局脑图
- 再看“状态结构”，理解系统里流动的是什么数据
- 再看“核心业务链路”：解析、检索、推荐
- 再看“增强能力”：记忆、工具、LLM、ReAct
- 最后看“收尾模块”：安全、格式化、配置

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

### 4. `src/cosmetics_agent/parser.py`

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

## 第五层：看底层数据源

### 5. `src/cosmetics_agent/catalog.py`

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

## 第六层：理解推荐引擎本身

### 6. `src/cosmetics_agent/recommender.py`

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

## 第七层：理解 RAG

### 7. `src/cosmetics_agent/rag.py`

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

## 第八层：理解记忆系统

### 8. `src/cosmetics_agent/memory.py`

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

## 第九层：理解工具本身

### 9. `src/cosmetics_agent/toolbox.py`

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

## 第十层：理解工具编排和 ReAct

### 10. `src/cosmetics_agent/research.py`

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

## 第十一层：理解 LLM 在系统里扮演什么角色

### 11. `src/cosmetics_agent/llm.py`

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

## 第十二层：理解安全边界

### 12. `src/cosmetics_agent/guardrails.py`

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

## 第十三层：理解最终输出怎么组织

### 13. `src/cosmetics_agent/formatter.py`

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

## 第十四层：最后看配置

### 14. `src/cosmetics_agent/config.py`

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

### 第三轮：看智能增强能力

读：

1. `memory.py`
2. `toolbox.py`
3. `research.py`
4. `llm.py`

目标：

- 理解记忆、工具、LLM、ReAct 是怎么叠加上去的

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

---

## 你学习时最值得观察的几个问题

1. 哪些地方是“规则驱动”的，哪些地方是“LLM 驱动”的？
2. 哪些地方在处理结构化状态，哪些地方在处理自然语言？
3. RAG 是怎么影响推荐排序的？
4. 记忆是怎么被读取、合并、写回的？
5. Tool calling 是怎么从“工具存在”变成“agent 会用工具”的？
6. ReAct 和普通 tool calling 的区别是什么？
7. guardrails 是在流程的哪个位置生效的？

---

## 看完这一轮后，你应该掌握什么

如果你把这份路线走完，你应该能清楚回答：

- 这个 agent 的主流程是什么
- 当前系统用了哪些 agent 技术
- 每种 agent 技术落在了哪些代码文件里
- 哪些模块属于“稳定底盘”，哪些模块属于“智能增强”
- 如果你下一步要继续加 Planner、Reflection、Vector Memory，应该改哪些地方

---

## 建议的下一步学习方向

等你把当前代码读顺之后，最推荐继续学这几个方向：

1. Reflection / Self-check
2. Planner / Task decomposition
3. Episodic memory
4. 向量化长期记忆
5. Tool result verification
6. Evaluation loop

如果你愿意，后面我还可以继续给你补一份：

`learning_advanced.md`

专门讲“接下来每一种 agent 技术应该怎么继续往这个项目里加”。
