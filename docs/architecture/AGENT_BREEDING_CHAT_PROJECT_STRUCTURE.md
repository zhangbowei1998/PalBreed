# 聊天式配种 Agent 项目目录结构设计

> 版本: v1.1 | 日期: 2026-08-01 | 状态: 开发设计基线（双项目版）
> 来源需求: AGENT_BREEDING_CHAT_REQUIREMENTS.md v1.1

---

## 1. 设计原则

1. 采用两个独立项目：Agent 服务项目 + 前端项目。
2. Agent 编排逻辑不放入现有 API 仓库路由中，避免职责混叠。
3. 前端只对接 Agent 服务，不直接依赖配种 API。
4. 测试按“单元 -> 集成 -> 对话回放”逐层覆盖。

---

## 2. 推荐目录结构（双项目）

```text
agent-service/
├── pyproject.toml
├── README.md
├── .env.example
├── src/
│   └── pl_agent_agent/
│       ├── app.py                              # Agent 服务入口（HTTP）
│       ├── config.py                           # 配置加载
│       ├── graph/
│       │   ├── workflow.py                     # LangGraph 主图定义
│       │   ├── nodes.py                        # 节点实现
│       │   ├── routes.py                       # 条件分支规则
│       │   └── guards.py                       # 深度/节点数/循环保护
│       ├── state/
│       │   ├── models.py                       # SessionState 数据结构
│       │   ├── repository.py                   # 状态存储接口
│       │   └── memory_store.py                 # MVP 内存存储实现
│       ├── clients/
│       │   ├── breeding_api_client.py          # 调用现有配种 API
│       │   ├── schemas.py                      # API DTO 与转换
│       │   └── errors.py                       # 外部调用错误映射
│       ├── interaction/
│       │   ├── actions.py                      # expand_parent/summarize_route
│       │   ├── click_protocol.py               # 点击协议
│       │   ├── presenter.py                    # 消息拼装
│       │   └── message_templates.py            # 文本模板
│       └── summarizer/
│           ├── route_builder.py                # 从 edges 构建路线图
│           ├── serializers.py                  # 结构化输出序列化
│           └── formatters.py                   # 文本树/graph_json 输出
│       ├── common/
│           ├── types.py
│           ├── constants.py
│           └── telemetry.py
├── tests/
│   ├── unit/
│   │   ├── test_workflow.py
│   │   ├── test_click_expand.py
│   │   └── test_route_summary.py
│   ├── integration/
│   │   ├── test_agent_with_api.py
│   │   └── test_recovery_flow.py
│   └── smoke/
│       └── test_agent_chat_smoke.py
└── docs/
  └── architecture/
    ├── AGENT_BREEDING_CHAT_REQUIREMENTS.md
    ├── AGENT_BREEDING_CHAT_ARCHITECTURE.md
    └── AGENT_BREEDING_CHAT_PROJECT_STRUCTURE.md

agent-web/
├── package.json
├── README.md
├── .env.example
├── src/
│   ├── agent/
│   │   ├── ChatActions.ts                      # 生成配种路线按钮行为
│   │   ├── ClickablePalItem.tsx                # 父母可点击组件
│   │   ├── RouteGraphPanel.tsx                 # 路线图展示
│   │   ├── protocol.ts                         # 前端动作协议
│   │   └── apiClient.ts                        # 调用 agent-service
│   ├── pages/
│   │   └── ChatPage.tsx
│   └── ...
├── tests/
│   ├── unit/
│   └── e2e/
└── docs/
  └── integration.md

pl-agent/                                        # 现有仓库（配种 API 与数据层）
└── packages/api                                 # 保持数据服务角色
```

---

## 3. 职责边界

## 3.1 agent-service

- 负责：意图编排、点击流转、状态管理、路线汇总。
- 不负责：数据库直连、配种算法核心 SQL、原始数据抓取。

## 3.2 pl-agent（现有 API 服务）

- 继续作为配种查询服务层。
- 对 agent-service 暴露稳定 HTTP 能力，不承载会话编排状态。

## 3.3 agent-web

- 负责 UI 原生点击、按钮触发、图可视化展示。
- 与 agent-service 的交互通过 action 协议，不直接耦合内部图节点。

---

## 4. 文件级设计说明

- graph/workflow.py
  - 定义 LangGraph 主图与节点连接关系。

- graph/guards.py
  - 实现 max_depth=10、max_nodes=200、重复点击阈值等规则。

- state/models.py
  - 定义 session_id、target_pal、target_candidates(top-3)、confirmed_target、edges、click_trace。

- clients/breeding_api_client.py
  - 封装 POST /api/query、GET /api/breeding/tree/{pal_id}、GET /api/pal/{pal_id}。

- interaction/click_protocol.py
  - 固化 action=expand_parent 的输入输出字段。

- summarizer/route_builder.py
  - 仅对已探索边构图（MVP explored_only），输出文本树和 graph_json。

---

## 5. 配置与环境变量建议

推荐新增环境变量（agent-service 使用）：

- AGENT_MAX_DEPTH=10
- AGENT_MAX_NODES=200
- AGENT_ROUTE_TIMEOUT_MS=8000
- AGENT_TOP_CANDIDATES=3
- BREEDING_API_BASE_URL=http://localhost:8000

推荐前端环境变量（agent-web 使用）：

- VITE_AGENT_SERVICE_BASE_URL=http://localhost:9000

---

## 6. 测试目录与策略

## 6.1 agent-service 单元测试（tests/unit）

- workflow 路由正确性
- 点击展开状态迁移
- 路线汇总输出稳定性
- guard 生效性（深度/节点/重复）

## 6.2 agent-service 集成测试（tests/integration）

- Agent 调 API 联调
- 并列 Top-3 确认流程
- 会话恢复一致性

## 6.3 agent-service 冒烟测试（tests/smoke/test_agent_chat_smoke.py）

覆盖主链路：

1. 用户问“手工等级最高的帕鲁怎么配种”
2. 返回 Top-3 候选并确认
3. 点击父母展开 3 层
4. 点击“生成配种路线”输出路线

---

## 7. 迁移与落地顺序

1. 新建 agent-service 项目骨架和基础 workflow。
2. 接入 API client 并跑通首问 + Top-3 确认。
3. 新建 agent-web 项目，接入聊天 UI 与点击协议。
4. 接入点击扩展与状态存储，联调路线汇总按钮。
5. 补齐两项目集成测试与端到端冒烟测试。

---

## 8. 文档索引（本专题）

- 需求文档: AGENT_BREEDING_CHAT_REQUIREMENTS.md
- 架构设计: AGENT_BREEDING_CHAT_ARCHITECTURE.md
- 目录结构: AGENT_BREEDING_CHAT_PROJECT_STRUCTURE.md

三者关系：需求定义“做什么”，架构定义“怎么做”，目录定义“放在哪”。
