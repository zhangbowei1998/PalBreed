# 05. state 包开发文档

## 1. 职责边界

`state` 负责“会话状态定义与持久化接口”。

负责：

- SessionState 结构定义
- 状态读写接口（Repository）
- 状态版本与并发更新策略

不负责：

- 业务流程分支
- 外部 API 调用
- 展示消息格式

## 2. 目标文件

- `models.py`: 状态模型
- `repository.py`: 抽象接口
- `memory_store.py`: MVP 实现

## 3. 状态字段建议

- `session_id`
- `target_pal`（最低持久化字段，当前确认目标）
- `target_candidates`（Top-3）
- `confirmed_target_pal`（可选冗余字段，需与 `target_pal` 保持一致）
- `explored_nodes`
- `edges`
- `click_trace`
- `limits`（depth/nodes）
- `meta`（version/updated_at）

## 4. Repository 接口建议

- `get(session_id)`
- `save(session_id, state)`
- `upsert(session_id, patch)`
- `append_edge(session_id, edge)`
- `append_click(session_id, click_event)`
- `reset(session_id)`

## 5. 一致性策略

- 使用 `version` 字段进行乐观锁（可选）。
- 同 session 并发 action 时按时间戳序列化处理。
- 保存失败不可吞错，必须返回上层并提示重试。

## 6. 测试建议

- 状态序列化/反序列化
- upsert 幂等性
- 并发冲突模拟
- reset 后状态清洁性
