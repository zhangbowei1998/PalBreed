# 08. summarizer 包开发文档

## 1. 职责边界

`summarizer` 负责“基于会话状态构建路线结果”。

负责：

- 从 `edges` 构建树/DAG
- 输出文本树
- 输出结构化 graph_json

不负责：

- 再次调用上游 API 补全（MVP）
- 会话状态写回
- 聊天动作分发

## 2. 目标文件

- `route_builder.py`: 图构建核心
- `serializers.py`: 结构化输出
- `formatters.py`: 文本树输出

## 3. 算法约束

- 模式：`explored_only`
- 排序：可展开优先 -> is_wild 优先 -> 名称稳定排序
- 限制：深度与节点数必须受 guard 约束

## 4. 输出契约

- `text_tree`: string
- `graph_json`:
  - `nodes[]`: {id, name, depth, status}
  - `edges[]`: {source, target, method}
  - `roots[]`: [target_pal_id]

## 5. 错误策略

- 无目标：返回 `MissingTargetError`
- 无边：返回“尚无可汇总路径”的可展示结果（非异常）
- 超时：返回部分结果与 `partial=true`

## 6. 测试建议

- 多分支图构建正确性
- 重复边去重
- 循环边保护
- 大图性能基准（节点 200）
