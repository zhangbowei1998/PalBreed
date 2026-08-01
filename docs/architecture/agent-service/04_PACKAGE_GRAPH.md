# 04. graph 包开发文档

## 1. 职责边界

`graph` 是编排核心，负责“流程如何走”，不负责“数据从哪来”与“最终怎么渲染页面”。

负责：

- LangGraph 节点编排与状态流转
- 条件分支决策（首问、确认、点击、汇总）
- 保护规则执行（深度、节点数、重复访问）

不负责：

- HTTP 协议
- 上游 API 实现细节
- 状态存储底层实现

## 2. 目标文件

- `workflow.py`: 图定义与入口
- `nodes.py`: 节点函数
- `routes.py`: 路由条件
- `guards.py`: 安全阈值规则

## 3. 节点清单（MVP）

1. `parse_intent`
2. `resolve_top_candidates`
3. `require_target_confirmation`
4. `query_parents`
5. `handle_expand_action`
6. `summarize_route`
7. `render_response`

## 4. 状态机约束

- 未确认目标前，禁止进入 `query_parents` 深挖。
- `expand_parent` 必须验证节点是否可展开。
- `summarize_route` 仅使用已探索边（explored_only）。

## 5. Guard 规则

- `max_depth=10`
- `max_nodes=200`
- `duplicate_expand_limit=3`
- `route_timeout_ms=8000`

## 6. 测试建议

- 节点级单测（输入状态 -> 输出状态）
- 路由分支覆盖测试
- guard 边界测试（depth=10, nodes=200）
- 会话恢复后继续执行测试
