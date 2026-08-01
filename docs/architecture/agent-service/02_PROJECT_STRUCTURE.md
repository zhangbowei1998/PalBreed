# 02. 项目目录结构

> 目标：定义 `agent-service` 的推荐目录、分层和依赖方向。

## 1. 推荐目录

```text
agent-service/
├── pyproject.toml
├── README.md
├── .env.example
├── src/
│   └── pl_agent_agent/
│       ├── app.py
│       ├── config.py
│       ├── graph/
│       │   ├── workflow.py
│       │   ├── nodes.py
│       │   ├── routes.py
│       │   └── guards.py
│       ├── state/
│       │   ├── models.py
│       │   ├── repository.py
│       │   └── memory_store.py
│       ├── clients/
│       │   ├── breeding_api_client.py
│       │   ├── schemas.py
│       │   └── errors.py
│       ├── interaction/
│       │   ├── actions.py
│       │   ├── click_protocol.py
│       │   ├── presenter.py
│       │   └── message_templates.py
│       ├── summarizer/
│       │   ├── route_builder.py
│       │   ├── serializers.py
│       │   └── formatters.py
│       └── common/
│           ├── types.py
│           ├── constants.py
│           └── telemetry.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── smoke/
└── docs/
    └── architecture/
        └── agent-service/
```

## 2. 依赖方向（必须）

- `app` -> `graph`
- `graph` -> `state`, `clients`, `interaction`, `summarizer`, `common`
- `summarizer` -> `state`, `common`
- `interaction` -> `common`
- `state` 不依赖 `graph/clients/interaction/summarizer`
- `clients` 不依赖 `graph/state/interaction/summarizer`

## 3. 高内聚低耦合约束

1. 跨包通信仅通过显式类型（DTO / TypedDict / dataclass）。
2. 禁止跨包直接访问内部模块（例如 `graph` 直接操作 `memory_store` 私有实现）。
3. 所有外部调用异常在 `clients/errors.py` 统一映射。
4. 状态变更只在 `state/repository.py` 接口定义路径内发生。

## 4. 包职责一览

- `app`: 协议接入层
- `graph`: 编排层
- `state`: 会话状态层
- `clients`: 外部服务访问层
- `interaction`: 输出消息层
- `summarizer`: 路线构建层
- `common`: 通用基础能力
