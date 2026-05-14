# Cosmetics Agent

Cosmetics Agent 是一个面向美妆与护肤导购场景的本地 Agent Demo。用户可以用自然语言描述自己的肤质、预算、功效诉求、使用场景和成分偏好，系统会结合商品库、知识库和联网工具，生成更适合的推荐结果，并补充购买入口。

当前项目提供两种使用方式：

- CLI：适合本地开发、调试和快速验证链路
- Web：适合以聊天界面演示完整的用户交互流程

## 项目特点

- 支持中文自然语言输入
- 支持基于肤质、预算、诉求和避雷成分的推荐
- 支持本地知识库检索增强
- 支持会话记忆与用户长期偏好记忆
- 支持联网查询商品线索与购买链接
- 支持多阶段 Agent 编排，输出更完整的推荐结论

## Quick Start

### 1. 安装依赖

```bash
pip install -e .
```

### 2. CLI 运行

单次问答：

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli chat --query "我是混油痘肌，预算300，想找清爽不闷痘的防晒。"
```

交互模式：

```bash
PYTHONPATH=src python3 -m cosmetics_agent.cli repl
```

### 3. Web 运行

```bash
PYTHONPATH=src python3.11 -m uvicorn cosmetics_agent.webapp:app --host 127.0.0.1 --port 8000
```

启动后打开：

[http://127.0.0.1:8000](http://127.0.0.1:8000)

## 可选环境变量

如果希望接入真实 LLM 与联网工具，可以在启动前配置：

```bash
export LLM_PROVIDER=ark
export ARK_API_KEY=your_api_key
export LLM_MODEL=your_model_id
export LIVE_TOOLS_ENABLED=1
```

然后再运行 CLI 或 Web 服务。

## 本地向量检索

项目现在支持本地 `Chroma` 持久化检索，不需要额外注册账号，默认会把向量索引保存在：

`/Users/jieruiliu/Cosmetics-Agent/.cosmetics_agent/chroma`

默认行为：

- 如果本地已安装 `chromadb`，知识库检索会自动走 `Chroma hybrid retrieval`
- 如果不可用，会自动回退到原来的规则/关键词检索，不影响项目运行

可选配置：

```bash
export VECTOR_STORE_ENABLED=1
export VECTOR_STORE_PROVIDER=chroma
export CHROMA_PERSIST_PATH=/your/local/path
export CHROMA_COLLECTION_NAME=knowledge_base
```

## Sample Input

```text
我是混油痘肌，夏天通勤想找一个清爽、不闷痘的防晒，预算 300 以内，尽量避开香精。
```

## Sample Output

```text
推荐结论：
优先考虑清爽型、成膜快、相对更适合混油皮日常通勤使用的防晒产品。

推荐商品：
1. 产品 A
特点：轻薄、成膜快、通勤友好
优势：更贴合混油痘肌诉求，预算友好
购买入口：淘宝 / 京东 / 天猫

2. 产品 B
特点：肤感清爽、后续上妆兼容度较好
优势：适合夏季日常场景
购买入口：淘宝 / 京东 / 天猫

使用提醒：
- 如果你近期正在爆痘或刷酸，建议优先做局部试用
- 如果对香精敏感，最终以下单页成分表为准
```

## 项目结构

```text
src/cosmetics_agent/
├── agent.py          # 主流程编排
├── multi_agent.py    # 多阶段 Agent 协作
├── parser.py         # 用户需求解析
├── recommender.py    # 商品筛选与排序
├── rag.py            # 知识库检索
├── memory.py         # 会话与用户记忆
├── toolbox.py        # 联网工具
├── research.py       # 商品与购买信息补充
├── llm.py            # LLM 接入
├── cli.py            # CLI 入口
└── webapp.py         # Web 服务入口
```

## Demo 说明

- 当前商品闭环以真实电商搜索入口为主，便于快速完成推荐到购买跳转
- 如果没有配置 LLM，系统会自动回退到本地规则与知识库模式
- 这是一个适合本地演示和产品原型展示的 Agent 项目
