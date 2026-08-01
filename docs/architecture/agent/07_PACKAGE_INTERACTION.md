# 07. interaction 包开发文档

## 1. 职责边界

`interaction` 负责“将业务结果变成前端可消费的消息与动作”。

负责：

- action 协议定义
- 消息模板渲染
- 点击节点的可执行动作生成

不负责：

- 上游数据查询
- 会话状态持久化
- 图编排路径选择

## 2. 目标文件

- `actions.py`: 动作枚举与构造器
- `click_protocol.py`: 点击协议
- `presenter.py`: 消息拼装
- `message_templates.py`: 文本模板

## 3. 动作协议建议

- `expand_parent`
  - payload: `pal_id`, `source_message_id`
- `summarize_route`
  - payload: `mode`, `session_id`
- `confirm_target`
  - payload: `pal_id`

## 4. 输出格式约束

- `messages[]`: 文本消息
- `actions[]`: 可点击动作
- `view_model`: 可视化组件数据（可选）

## 5. 文案策略

- 明确下一步可操作动作
- 失败提示给出恢复建议
- 重复节点提示“已复用历史结果”

## 6. 测试建议

- 模板渲染快照测试
- 动作 payload 完整性测试
- 多语言/文案 fallback 测试（如后续需要）
