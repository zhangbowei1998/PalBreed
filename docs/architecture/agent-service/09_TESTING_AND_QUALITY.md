# 09. 测试与质量文档

## 1. 测试分层

1. 单元测试（unit）
- 每包纯逻辑验证

2. 集成测试（integration）
- graph 与 clients/state/interaction/summarizer 协同

3. 冒烟测试（smoke）
- 关键对话链路全流程

## 2. 最小测试矩阵

- 首问并列 Top-3
- 目标确认后展开
- 连续点击 5 轮
- 重复点击同节点
- 生成路线成功
- 上游超时恢复
- 原生点击不可用时 `/expand <pal_id>` 降级可用

## 3. 质量门禁

- 单测覆盖率建议 >= 80%
- 关键路径集成测试必须全绿
- 冒烟场景每日运行
- 变更必须附带契约测试更新

## 4. 日志与追踪

必打字段：

- `session_id`, `action`, `latency_ms`, `depth`, `node_count`, `error_code`

建议接入：

- request_id 贯通（前端 -> agent-service -> 上游 API）

## 5. 回归策略

- 固定测试数据集（最少 5 组）
- 每次策略变更回放历史对话样例
- 新增 guard 参数必须补边界测试
