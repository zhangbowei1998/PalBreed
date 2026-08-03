# agent 模块开发文档索引

> 版本: v1.1 | 日期: 2026-08-01 | 状态: 已实现（MVP）

本目录为 agent 模块（`packages/agent` + `packages/agent-web`）专项开发文档。
当前代码已落地 MVP，可直接运行、测试和继续扩展。

## 代码入口

- 服务入口：`packages/agent-web/pl_agent/agent_web/app.py`
- 编排入口：`packages/agent/pl_agent/agent/graph/workflow.py`
- 状态存储：`packages/agent/pl_agent/agent/state/memory_store.py`
- 上游调用：`packages/agent/pl_agent/agent/clients/breeding_api_client.py`
- 认证路由：`packages/agent-web/pl_agent/agent_web/auth/routes.py`

## 统一命令入口

- 启动：`make serve-agent-service`
- agent 模块测试：`make test-agent`
- agent-web 服务测试：`make test-agent-web`
- 根项目全量：`make test-all`

## 文档清单

- [01. 服务总体设计](./01_SERVICE_OVERVIEW.md)
- [02. 项目目录结构](./02_PROJECT_STRUCTURE.md)
- [03. app 包开发文档](./03_PACKAGE_APP.md)
- [04. graph 包开发文档](./04_PACKAGE_GRAPH.md)
- [05. state 包开发文档](./05_PACKAGE_STATE.md)
- [06. clients 包开发文档](./06_PACKAGE_CLIENTS.md)
- [07. interaction 包开发文档](./07_PACKAGE_INTERACTION.md)
- [08. summarizer 包开发文档](./08_PACKAGE_SUMMARIZER.md)
- [09. 测试与质量文档](./09_TESTING_AND_QUALITY.md)
- [10. 交付与里程碑](./10_DELIVERY_PLAN.md)

## 约束原则

1. 高内聚：每个包只负责一类变化原因。
2. 低耦合：包间通过 DTO、接口和动作协议通信，避免跨包直接读写内部结构。
3. 可替换：状态存储、上游 API、渲染器均可通过接口替换。
4. 可测试：每包至少具备单元测试入口，集成测试只验证包间契约。

## 依赖关系（简图）

```mermaid
flowchart LR
  app --> graph
  graph --> state
  graph --> clients
  graph --> interaction
  graph --> summarizer
  summarizer --> state
```

> 说明：`graph` 是编排中心，其他包为能力模块。`app` 仅负责协议接入与请求分发。

## 当前实现范围（MVP + 扩展）

1. `POST /agent/chat`：LLM function calling 聊天（支持“手工最高”、Top-3 候选、文本降级指令）+ 10 个工具（配种/详情/技能/被动/掉落/配方/Text-to-SQL）。
2. `POST /agent/action`：支持 `confirm_target`、`expand_parent`、`select_parent_pair`、`continue_from_parent`。
3. `GET /agent/session/{session_id}`：支持会话快照读取。
4. 状态守卫：深度上限、节点上限、重复展开阈值。
5. 汇总输出：`text_tree` + `graph_json`（explored_only）。
6. 记忆系统：短期（会话）+ 长期（PG/file，按用户）+ LLM 上下文压缩。
7. 用户体系：`/auth/register|login|me`，token 认证，长期记忆按用户隔离。
8. 可观测：`/admin/traces` + `/admin/monitor`（PostgresTraceStore / InMemoryTraceStore 降级）。
9. 数据卡片：`data_cards`（被动/掉落/配方/技能/详情）随 chat 返回，前端渲染。

## 后续扩展建议

1. 将 `state` 从内存实现切换到 Redis。
2. 增加 `auto_complete` 路线补全模式（受阈值保护）。
3. 多代配种规划（见 `docs/decisions/003-feature-gaps.md`）。
