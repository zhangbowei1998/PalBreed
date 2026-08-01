# 02. 项目目录结构

> 目标：定义 agent 模块的推荐目录、分层和依赖方向。

## 1. 推荐目录

```text
packages/agent/                 ← 🤖 独立 agent 模块（无 web 框架依赖）
├── pyproject.toml
├── README.md
├── .env.example
├── data/                       ← 本地数据（file 模式记忆/用户）
├── demo/
│   └── llm_tools_demo.py
└── pl_agent/
    └── agent/
        ├── __init__.py
        ├── config.py           ← 运行时配置 + .env 加载
        ├── llm/                ← LLM 客户端抽象（DeepSeek / OpenAI 兼容）
        │   ├── base.py         ←   LLMClient 抽象 + ChatMessage/LLMResponse
        │   ├── deepseek.py     ←   OpenAI 兼容实现
        │   ├── factory.py      ←   按 provider 创建
        │   └── __tests__/
        ├── tools/              ← function calling 工具
        │   ├── base.py         ←   Tool 抽象 + ToolError
        │   ├── registry.py     ←   ToolRegistry
        │   └── breeding.py     ←   配种/解析/统计工具
        ├── memory/             ← 长期记忆 + 上下文压缩
        │   ├── long_term.py    ←   LongTermMemory (file)
        │   ├── postgres.py     ←   PostgresLongTermMemory
        │   └── compress.py     ←   summarize_history (LLM 摘要)
        ├── graph/              ← 编排中心
        │   ├── workflow.py     ←   AgentWorkflow 入口
        │   ├── agent_loop.py   ←   LLM function calling 循环
        │   ├── nodes.py        ←   配种节点
        │   └── guards.py       ←   状态守卫
        ├── state/
        │   ├── models.py       ←   SessionState / ChatTurn
        │   ├── repository.py   ←   仓库抽象
        │   └── memory_store.py ←   内存实现
        ├── clients/
        │   ├── breeding_api_client.py
        │   ├── schemas.py
        │   └── errors.py
        ├── interaction/
        │   ├── actions.py
        │   ├── click_protocol.py
        │   ├── presenter.py
        │   └── message_templates.py
        ├── auth/               ← 用户核心（无 FastAPI 路由）
        │   ├── models.py       ←   User / UserStore / FileUserStore
        │   ├── security.py     ←   密码哈希 + token 签发
        │   └── postgres.py     ←   PostgresUserStore
        ├── summarizer/
        │   ├── route_builder.py
        │   ├── serializers.py
        │   └── formatters.py
        ├── intent/             ← 意图识别（LLM + 规则回退）
        │   ├── recognizer.py
        │   └── schemas.py
        ├── prompts/            ← 📝 所有 LLM 提示词（独立 .md 便于阅读/优化）
        │   ├── __init__.py     ←   importlib.resources 加载导出
        │   ├── assistant.md           主配种助手
        │   ├── intent_recognizer.md   意图识别器
        │   └── context_compress.md    对话历史压缩
        └── common/
            ├── types.py
            ├── constants.py
            └── telemetry.py

packages/agent-web/             ← 🌐 FastAPI 服务层（服务前端）
├── pyproject.toml
└── pl_agent/
    └── agent_web/
        ├── app.py              ← FastAPI 入口 + lifespan + 路由
        └── auth/
            └── routes.py       ← /auth/register | /auth/login | /auth/me
```

## 2. 依赖方向（必须）

- `agent-web.app` -> `agent.graph`（workflow）、`agent.auth`、`agent.llm`、`agent.memory`
- `graph` -> `state`, `clients`, `interaction`, `summarizer`, `common`, `llm`, `tools`, `memory`
- `summarizer` -> `state`, `common`
- `interaction` -> `common`
- `state` 不依赖 `graph/clients/interaction/summarizer`
- `clients` 不依赖 `graph/state/interaction/summarizer`
- `agent` 不依赖 FastAPI / uvicorn（纯逻辑）
- `agent-web` 依赖 `agent`（workspace）+ fastapi + uvicorn

## 3. 高内聚低耦合约束

1. 跨包通信仅通过显式类型（DTO / TypedDict / dataclass）。
2. 禁止跨包直接访问内部模块（例如 `graph` 直接操作 `memory_store` 私有实现）。
3. 所有外部调用异常在 `clients/errors.py` 统一映射。
4. 状态变更只在 `state/repository.py` 接口定义路径内发生。
5. `agent` 内的认证核心不持有 FastAPI 路由；路由在 `agent-web.auth.routes`。

## 4. 包职责一览

- `agent-web.app`: 协议接入层（HTTP）
- `agent-web.auth.routes`: 认证 HTTP 路由
- `agent.graph`: 编排层
- `agent.state`: 会话状态层
- `agent.clients`: 外部服务访问层
- `agent.interaction`: 输出消息层
- `agent.summarizer`: 路线构建层
- `agent.llm`: LLM 客户端抽象
- `agent.tools`: function calling 工具
- `agent.memory`: 长期记忆 + 上下文压缩
- `agent.auth`: 用户核心（存储/密码/token）
- `agent.common`: 通用基础能力
