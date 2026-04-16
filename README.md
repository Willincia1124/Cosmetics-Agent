# Cosmetics Agent

一个可在本地 terminal 中运行的美妆导购 agent MVP。它会根据用户输入的肤质、预算、场景、功效诉求和成分偏好，给出护肤/彩妆推荐，并在信息不足时主动追问。

## 当前能力

- 解析中文自然语言需求
- 提取用户画像：肤质、预算、场景、功效、成分偏好/禁忌
- 从内置产品库筛选候选商品
- 从本地知识库做轻量 RAG 检索，补充推荐依据
- 用规则打分并生成推荐理由
- 支持接入 LLM API 做画像增强与候选复核，默认优先适配 OpenRouter 免费路由
- 支持 live tool calling：联网检索商品信息并补充购买链接
- 支持可观察的 ReAct 模式：展示思考摘要、动作和观察结果
- 支持 SQLite 持久化短期记忆与长期记忆
- 支持显式多 Agent 架构：主控协调 + 画像分析 + 诉求分析 + 商品筛选 + 购买信息收集 + 安全复核 + 最终自检
- 支持 Planner：在执行前生成清晰的任务计划
- 支持 Self-check：在最终输出前做一致性和约束复核
- 支持离线 Eval：基于固定测试集自动评估预算、品类、风险提示、追问、RAG、Planner、自检等能力
- 做基础安全检查，避免明显不合适的推荐
- 支持 CLI 本地测试

## 快速开始

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli chat --query "我是混油痘肌，预算300，想找清爽不闷痘的防晒"
```

进入交互模式：

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli repl
```

查看帮助：

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli --help
```

单独查看 RAG 检索结果：

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli kb --query "混油皮通勤底妆，预算300，想要雾面持妆"
```

跑离线评测：

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli eval
```

如果你想省掉 `PYTHONPATH=src`，也可以先执行：

```bash
pip install -e .
```

## Web 入口

现在项目除了 CLI，也支持一个最小可用的 Web 入口，适合直接体验聊天式交互。

启动方式：

```bash
pip install -e .
PYTHONPATH=src python3.11 -m uvicorn cosmetics_agent.webapp:app --reload
```

启动后打开：

[http://127.0.0.1:8000](http://127.0.0.1:8000)

当前 Web 版支持：

- 聊天式用户入口
- 推荐结果卡片展示
- Planner / Self-check / Tool Calling 信息展示
- 基础会话记忆查看
- 当前 session 重置

如果你想让 Web 版也走 LLM 和 live tools，可以先设置环境变量再启动：

```bash
export LLM_PROVIDER=ark
export ARK_API_KEY=你的_key
export LLM_MODEL=你的方舟模型ID或推理接入点ID
export LIVE_TOOLS_ENABLED=1
PYTHONPATH=src python3.11 -m uvicorn cosmetics_agent.webapp:app --reload
```

## 记忆系统

当前内置了一个简单但完整的记忆层，默认落盘到：

`/Users/jieruiliu/Cosmetics-Agent/.cosmetics_agent/memory.db`

包含两类记忆：

- 短期记忆：按 `session_id` 保存最近消息；超过 `message_window` 后，旧消息会被压缩进会话摘要
- 长期记忆：按 `user_id` 保存稳定画像和偏好条目

示例：

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli repl --session-id demo-session --user-id demo-user --message-window 4
```

查看当前记忆：

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli memory --session-id demo-session --user-id demo-user --message-window 4
```

## 接入免费 LLM API

当前代码默认优先支持 `OpenRouter` 的免费路由，同时兼容 `火山方舟/豆包`、`Groq` 和 `Together` 的 OpenAI 兼容接口。

如果你想先走国产模型，推荐优先接 `豆包（火山方舟）`。

豆包 / 火山方舟示例：

```bash
export LLM_PROVIDER=ark
export ARK_API_KEY=你的_key
export LLM_MODEL=你的方舟模型ID或推理接入点ID
PYTHONPATH=src python3 -m cosmetics_agent.cli chat --query "我是混油痘肌，预算300，想找清爽不闷痘的防晒"
```

说明：

- 默认接口地址是 `https://ark.cn-beijing.volces.com/api/v3/chat/completions`
- 如果你使用别的地域或网关，可以额外设置 `ARK_BASE_URL`
- `LLM_MODEL` 建议填你在火山方舟里实际可调用的模型 ID 或推理接入点 ID

推荐先试 OpenRouter：

```bash
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY=你的_key
export LLM_MODEL=openrouter/free
PYTHONPATH=src python3 -m cosmetics_agent.cli chat --query "我是混油痘肌，预算300，想找清爽不闷痘的防晒"
```

如果你想用 Groq：

```bash
export LLM_PROVIDER=groq
export GROQ_API_KEY=你的_key
export LLM_MODEL=openai/gpt-oss-20b
PYTHONPATH=src python3 -m cosmetics_agent.cli chat --query "我是混油痘肌，预算300，想找清爽不闷痘的防晒"
```

如果环境变量没配，程序会自动回退到纯规则 + RAG 模式。

## 开启 Live Tools

如果你想让 agent 联网查商品页和购买链接：

```bash
export LIVE_TOOLS_ENABLED=1
PYTHONPATH=src python3 -m cosmetics_agent.cli chat --query "混油皮，想找通勤底妆，预算300"
```

当前 live tools 提供这几个能力：

- `search_web`：查品牌、产品和网页资料
- `search_products`：查商品页
- `extract_product_info`：提取网页标题、摘要和价格线索
- `get_purchase_links`：给推荐结果补购买链接

开启 live tools 后，agent 会额外输出一段 `ReAct 轨迹`，方便你观察：

- 它为什么决定调某个工具
- 调完之后观察到了什么
- 为什么继续下一步或停止

说明：

- 这版 live tools 主要依赖公共网页搜索结果，适合学习和搭链路
- 返回链接时会尽量优先常见电商或品牌官网
- 如果网络不可用，agent 会保留原来的本地推荐，不会直接失败

## Eval 与效果评估

这次新增了一套本地可重复运行的离线评测，入口是：

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli eval
```

如果你只想跑单个 case：

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli eval --case-id sunscreen_oily_budget
```

默认数据集在：

`/Users/jieruiliu/Cosmetics-Agent/data/eval_dataset.jsonl`

当前这套 eval 为什么重要：

- 它不是只看“回答像不像”，而是拆成一组可解释指标
- 你后面每加一种 agent 技术，都可以在同一批 case 上重跑
- 这样你能更客观地比较“多 agent / planner / self-check / RAG”到底有没有带来提升

当前第一版评测指标主要包括：

- `has_recommendation`：有没有真的给出候选商品
- `category_match`：主推荐品类是否正确
- `budget_ok`：主推荐是否遵守预算
- `avoid_ingredient_ok`：是否避开用户明确禁忌成分
- `clarification_present`：信息不完整时是否主动追问
- `safety_note_present`：高风险或敏感场景下是否给出提醒
- `rag_used`：是否真的命中了知识库
- `planner_used`：是否生成执行计划
- `self_check_used`：是否执行最终自检

这套 eval 的设计思路是“先做规则型离线评测，再考虑 LLM judge”：

- 规则型评测更稳定，适合你现在边做边学
- 它非常适合做版本对比，不容易被模型波动干扰
- 等后面系统更复杂时，再补 LLM-as-a-judge 会更合适

## 系统设计

这一节用于帮助你从 agent 技术角度理解当前代码。建议直接在本地编辑器里打开本 README 查看 Mermaid 图，会比聊天窗口里更清楚。

### 系统架构图

```mermaid
flowchart TB

    U[User]
    CLI[CLI Interface<br/>src/cosmetics_agent/cli.py]
    AGENT[BeautyAdvisorAgent<br/>src/cosmetics_agent/agent.py]

    U --> CLI
    CLI --> AGENT

    subgraph INPUT["1. Input And State"]
        PARSER[Parser<br/>src/cosmetics_agent/parser.py]
        MEMORY[Memory Manager<br/>src/cosmetics_agent/memory.py]
        PROFILE[Structured UserProfile]
    end

    subgraph MEMORY_DB["2. Persistent Memory"]
        STS[session_state<br/>SQLite]
        STM[session_messages<br/>SQLite]
        UPROF[user_profiles<br/>SQLite]
        UMEM[user_memories<br/>SQLite]
        COMP[Compression Logic<br/>keep recent K messages<br/>compress older turns]
    end

    subgraph KNOWLEDGE["3. Knowledge And Data"]
        CATALOG[Product Catalog<br/>src/cosmetics_agent/catalog.py]
        RAG[RAG Retriever<br/>src/cosmetics_agent/rag.py]
        KB[knowledge_base.jsonl]
        RECSCORE[Recommender / Scoring<br/>src/cosmetics_agent/recommender.py]
    end

    subgraph LLM_LAYER["4. LLM Reasoning Layer"]
        LLM[LLMClient<br/>src/cosmetics_agent/llm.py]
        ENHANCE[Profile Enhancement]
        RERANK[Rerank And Explain]
        REACT_LLM[LLM-driven ReAct Planner]
    end

    subgraph SKILLS["5. Planned Skill Layer"]
        SK1[task-decomposition-and-handoff<br/>for TaskCoordinator]
        SK2[skin-profile-analysis<br/>for ProfileAnalysisAgent]
        SK3[need-clarification<br/>for NeedAnalysisAgent]
        SK4[product-matching-and-ranking<br/>for ProductSelectionAgent]
        SK5[shopping-link-collection<br/>for PurchaseLinkAgent]
        SK6[ingredient-safety-review<br/>for SafetyReviewerAgent]
    end

    subgraph TOOLS["6. Tool Calling Layer"]
        RESEARCH[ResearchOrchestrator<br/>src/cosmetics_agent/research.py]
        TOOLBOX[ResearchToolbox<br/>src/cosmetics_agent/toolbox.py]
        TWEB[search_web]
        TPROD[search_products]
        TEXTRACT[extract_product_info]
        TLINK[get_purchase_links]
        INTERNET[Internet / Search / Product Pages]
    end

    subgraph SAFETY["7. Safety And Output"]
        GUARD[Guardrails<br/>src/cosmetics_agent/guardrails.py]
        FORMAT[Formatter<br/>src/cosmetics_agent/formatter.py]
        RESP[AgentResponse]
        OUT[Rendered CLI Output]
    end

    AGENT --> PARSER
    AGENT --> MEMORY

    PARSER --> PROFILE
    MEMORY --> PROFILE

    MEMORY --> STS
    MEMORY --> STM
    MEMORY --> UPROF
    MEMORY --> UMEM
    STM --> COMP
    COMP --> STS

    PROFILE --> RAG
    RAG --> KB
    PROFILE --> RECSCORE
    CATALOG --> RECSCORE
    KB --> RAG
    RAG --> RECSCORE

    AGENT --> LLM
    LLM --> ENHANCE
    LLM --> RERANK
    LLM --> REACT_LLM

    AGENT --> SK1
    AGENT --> SK2
    AGENT --> SK3
    AGENT --> SK4
    AGENT --> SK5
    AGENT --> SK6

    PROFILE --> ENHANCE
    ENHANCE --> PROFILE
    RECSCORE --> RERANK

    AGENT --> RESEARCH
    RESEARCH --> TOOLBOX
    REACT_LLM --> RESEARCH

    TOOLBOX --> TWEB
    TOOLBOX --> TPROD
    TOOLBOX --> TEXTRACT
    TOOLBOX --> TLINK

    TWEB --> INTERNET
    TPROD --> INTERNET
    TEXTRACT --> INTERNET
    TLINK --> INTERNET

    RECSCORE --> RESP
    RERANK --> RESP
    RESEARCH --> RESP
    PROFILE --> RESP

    RESP --> GUARD
    GUARD --> FORMAT
    FORMAT --> OUT
    OUT --> U

    RESP --> MEMORY
```

### 端到端 Workflow 图

```mermaid
flowchart TB

    A[User Sends Query] --> B[CLI Receives Input]
    B --> C[BeautyAdvisorAgent.run]

    C --> D[Parse Query]
    D --> D1[Extract Skin Type]
    D --> D2[Extract Budget]
    D --> D3[Extract Category]
    D --> D4[Extract Concerns / Ingredients / Finish]
    D --> E[Initial UserProfile]

    C --> F[Load Short-term Memory]
    F --> F1[Load Session Summary]
    F --> F2[Load Recent Messages]

    C --> G[Load Long-term Memory]
    G --> G1[Load Stable User Profile]
    G --> G2[Load Preference Memories]

    E --> H[Merge Memory Into Profile]
    F --> H
    G --> H

    H --> I[Build Clarifying Questions]
    H --> J[Run RAG Retrieval]

    J --> J1[Build Retrieval Terms]
    J1 --> J2[Search Knowledge Base]
    J2 --> J3[Score Knowledge Chunks]
    J3 --> J4[Select Top-K Chunks]

    J4 --> K{LLM Configured?}

    K -- Yes --> L[LLM Enhance Profile]
    L --> L1[Refine Hidden Preferences]
    L1 --> L2[Re-run RAG With Refined Profile]

    K -- No --> M[Skip LLM Profile Enhancement]

    L2 --> N[Retrieve Candidate Products]
    M --> N

    N --> O[Rule-based Recommendation Scoring]
    O --> O1[Budget Match]
    O --> O2[Skin Match]
    O --> O3[Concern Match]
    O --> O4[Ingredient Match / Avoid]
    O --> O5[Finish / Scenario Match]
    O --> O6[RAG Evidence Bonus]

    O --> P[Initial Recommendations]

    P --> Q{LLM Configured?}
    Q -- Yes --> R[LLM Rerank And Explain]
    Q -- No --> S[Keep Rule Ranking]

    R --> T[Recommendation Set]
    S --> T

    T --> U{Live Tools Enabled?}

    U -- No --> V[Skip Tool Enrichment]

    U -- Yes --> W{LLM Available For ReAct?}

    W -- Yes --> X[LLM-driven ReAct Loop]
    X --> X1[Thought]
    X1 --> X2[Choose Action]
    X2 --> X3[Call Tool]
    X3 --> X4[Observe Result]
    X4 --> X5{Continue?}
    X5 -- Yes --> X1
    X5 -- No --> X6[Finish ReAct]

    W -- No --> Y[Heuristic ReAct Loop]
    Y --> Y1[Thought]
    Y1 --> Y2[get_purchase_links]
    Y2 --> Y3[Optional extract_product_info]
    Y3 --> Y4[Observation]
    Y4 --> Y5[Finish]

    X6 --> Z[Attach Purchase Links / Live Insights / ReAct Trace]
    Y5 --> Z
    V --> Z

    Z --> AA[Guardrails]
    AA --> AB[Assemble AgentResponse]

    AB --> AC[Persist Memory]
    AC --> AC1[Save User Message]
    AC --> AC2[Save Assistant Note]
    AC --> AC3[If Message Count > K<br/>Compress Older Turns Into Summary]
    AC --> AC4[Update Long-term Profile]
    AC --> AC5[Write Long-term Preference Memories]

    AB --> AD[Format Output]
    AD --> AE[Render User-facing Result]
    AE --> AF[User Sees Recommendations]
```

### 当前 Agent 技术和代码映射

- 多阶段编排：`src/cosmetics_agent/agent.py`
- 多 Agent 架构：`src/cosmetics_agent/multi_agent.py`
- 需求解析：`src/cosmetics_agent/parser.py`
- 短期记忆与长期记忆：`src/cosmetics_agent/memory.py`
- 本地知识库 RAG：`src/cosmetics_agent/rag.py`
- 规则推荐与排序：`src/cosmetics_agent/recommender.py`
- LLM 画像增强 / 复核 / ReAct：`src/cosmetics_agent/llm.py`
- Tool calling：`src/cosmetics_agent/toolbox.py` + `src/cosmetics_agent/research.py`
- Guardrails：`src/cosmetics_agent/guardrails.py`
- 最终可解释输出：`src/cosmetics_agent/formatter.py`
- 离线评测：`src/cosmetics_agent/evals.py` + `data/eval_dataset.jsonl`

### 当前多 Agent 角色

当前系统已经拆成这些显式角色：

- `RequestPlannerAgent`：在真正执行前生成任务计划
- `TaskCoordinator`：主控协调，负责拆解任务和串联各角色
- `ProfileAnalysisAgent`：分析用户当前状态、肤质特征和个体画像
- `NeedAnalysisAgent`：分析用户当前诉求、缺失信息和决策重点
- `ProductSelectionAgent`：结合产品库、RAG 和排序逻辑筛选商品
- `PurchaseLinkAgent`：收集购买链接、网页摘要和实时线索
- `SafetyReviewerAgent`：做风险和约束复核
- `ReflectionAgent`：在最终输出前做 self-check

### 当前每个 Agent 最值得先做的 1 个 Skill

下面这 8 个 skill 目前是“推荐设计”，还没有真正作为独立 skill 文件接进运行时，但我建议后续优先按这套方向落地：

- `RequestPlannerAgent` -> `request-planning`
  作用：在执行前生成清晰计划，定义步骤顺序和目标
- `TaskCoordinator` -> `task-decomposition-and-handoff`
  作用：把用户请求拆成可执行子任务，并明确交接顺序与停止条件
- `ProfileAnalysisAgent` -> `skin-profile-analysis`
  作用：稳定分析肤质、当前状态、长期特征和记忆融合方式
- `NeedAnalysisAgent` -> `need-clarification`
  作用：识别核心诉求、缺失信息和最小必要追问
- `ProductSelectionAgent` -> `product-matching-and-ranking`
  作用：统一产品匹配、排序优先级和 RAG 证据使用方法
- `PurchaseLinkAgent` -> `shopping-link-collection`
  作用：规范查链接、选链接、回退策略和平台优先级
- `SafetyReviewerAgent` -> `ingredient-safety-review`
  作用：统一做禁忌成分、敏感场景和风险提示的复核
- `ReflectionAgent` -> `final-constraint-self-check`
  作用：在最终输出前统一检查预算、禁忌、缺失信息和整体一致性

这些 skill 最适合承载：

- 稳定的方法论
- 输入输出规范
- 决策优先级
- 失败回退规则

为什么我额外加了 `SafetyReviewerAgent`：

- 在美妆/护肤场景里，“更智能”不只是更会推荐，还包括更会规避不合适建议
- 它能让多 Agent 架构更接近真实顾问型系统，而不是单纯商品检索器

为什么我又加了 `Planner` 和 `Reflection`：

- `Planner` 负责回答“接下来该按什么顺序做”
- `Reflection` 负责回答“最后这份结果是否真的站得住”
- 这两个能力是 agent 从“能做事”走向“更可靠、更可解释”的关键

为什么现在又加了 `Eval`：

- 你后面会不断往系统里叠加 agent 技术
- 如果没有固定测试集，很容易只凭感觉判断“更智能了”
- eval 让你能稳定比较改动前后在预算、品类、风险提示和追问这些维度上的变化

### 如何从学习角度阅读当前代码

推荐按这个顺序看：

1. `src/cosmetics_agent/agent.py`
2. `src/cosmetics_agent/models.py`
3. `src/cosmetics_agent/parser.py`
4. `src/cosmetics_agent/recommender.py`
5. `src/cosmetics_agent/rag.py`
6. `src/cosmetics_agent/memory.py`
7. `src/cosmetics_agent/toolbox.py`
8. `src/cosmetics_agent/research.py`
9. `src/cosmetics_agent/llm.py`
10. `src/cosmetics_agent/formatter.py`

## 推荐的下一步

- 把当前启发式 tool policy 升级成真正由 LLM 决策的 tool calling
- 把当前关键词检索升级为向量检索
- 增加产品库与成分库
- 给 eval 增加 LLM judge、回归对比和多版本横向比较
- 对接 API / Web 界面
