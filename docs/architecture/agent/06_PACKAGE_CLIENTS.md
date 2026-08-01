# 06. clients 包开发文档

## 1. 职责边界

`clients` 负责“访问外部服务（现有配种 API）并做 DTO 映射”。

负责：

- HTTP 请求发送
- 超时重试与错误分类
- 响应结构校验与映射

不负责：

- 会话状态变更
- 业务流程分支
- 消息展示模板

## 2. 目标文件

- `breeding_api_client.py`: API 访问封装
- `schemas.py`: 入参/出参 DTO
- `errors.py`: 异常定义与映射

## 3. 能力接口建议

- `query_top_suitability(work_type, level)`
- `get_parent_pairs(pal_id)`
- `get_pal_detail(pal_id)`

## 4. 失败处理策略

- 连接超时：重试 1 次
- 4xx：直接上抛业务异常
- 5xx：包装为 `UpstreamServiceError`
- 无效响应：`InvalidPayloadError`

## 5. 可测试性要求

- 所有 HTTP 调用通过可注入 client 实例
- DTO 映射纯函数化
- 错误映射具备完整分支测试

## 6. 测试建议

- Mock HTTP 成功/失败场景
- timeout 与 retry 验证
- 结构缺失字段容错测试
