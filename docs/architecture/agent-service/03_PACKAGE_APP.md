# 03. app 包开发文档

## 1. 职责边界

`app` 负责“协议接入与请求生命周期管理”，不承载业务推理。

负责：

- HTTP 路由与请求校验
- session_id 提取/生成
- 调用 graph 执行入口
- 统一响应封装和错误码映射

不负责：

- 业务节点分支决策
- 上游 API 调用细节
- 会话状态存储实现

## 2. 目标文件

- `app.py`: 服务启动、路由注册
- `config.py`: 配置加载

## 3. 输入输出契约

- `POST /agent/chat` 输入必须验证：`session_id`, `message`
- `POST /agent/action` 输入必须验证：`session_id`, `action`
- `POST /agent/action` 条件校验：
  - `action=expand_parent` 时校验 `pal_id`, `source_message_id`
  - `action=summarize_route` 时校验 `mode`
- 输出统一结构：
  - `messages`: 展示消息数组
  - `actions`: 可执行动作数组
  - `state_snapshot`: 最小状态快照
  - `meta`: 调试与性能字段

## 4. 异常策略

- 400: 参数校验失败
- 409: 状态冲突（未确认目标就请求展开）
- 424: 上游 API 失败
- 500: 未知异常

## 5. 测试建议

- 路由参数校验单测
- 错误码映射单测
- 请求幂等性测试（重复 action）
