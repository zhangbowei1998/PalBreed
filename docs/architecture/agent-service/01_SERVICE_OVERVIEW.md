# 01. 服务总体设计

> 目标：定义 `agent-service` 的系统边界、运行模型与对外契约。

## 1. 服务定位

`agent-service` 是聊天式配种体验的业务编排层，负责：

1. 接收用户聊天输入和动作事件。
2. 基于 LangGraph 执行业务流转。
3. 调用上游配种 API 获取数据。
4. 维护会话状态并输出可展示消息。

不负责：

- 数据库直连与配种 SQL
- 前端组件渲染
- 原始数据采集

## 2. 外部依赖

- 上游服务：`pl-agent` API（HTTP）
- 调用接口：
  - `POST /api/query`
  - `GET /api/breeding/tree/{pal_id}`
  - `GET /api/pal/{pal_id}`

## 3. 对外接口（agent-service）

建议最小接口集：

1. `POST /agent/chat`
- 入参：`session_id`, `message`, `context`
- 出参：`messages`, `actions`, `state_snapshot`

2. `POST /agent/action`
- 入参：`session_id`, `action`, `pal_id?`, `source_message_id?`, `mode?`
- 约束：
  - `action=expand_parent` 时必填 `pal_id`, `source_message_id`
  - `action=summarize_route` 时必填 `mode`（MVP 固定 `explored_only`）
- 出参：`messages`, `actions`, `state_snapshot`

3. `GET /agent/session/{session_id}`
- 入参：路径参数 `session_id`
- 出参：`state_snapshot`

## 4. 关键业务策略

- 最高等级并列：返回 Top-3 并要求用户确认。
- 点击协议：优先 UI 原生点击；动作名统一 `expand_parent`。
- 路线生成：MVP 仅汇总已探索分支（`explored_only`）。
- 安全阈值：`max_depth=10`, `max_nodes=200`, `route_timeout=8s`。

## 5. 可扩展点

- 状态存储实现：内存 -> Redis -> 持久化数据库
- 模型能力：规则解析 -> LLM 辅助解析
- 路线输出：文本树 -> 图结构 -> 可视化元数据增强
