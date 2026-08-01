# agent-service

独立的聊天式配种 Agent 服务。

## 快速启动

1. 安装依赖
   - `uv sync`
2. 启动服务
   - `uv run uvicorn pl_agent_agent.app:app --reload --port 9000`

## 环境变量

- `BREEDING_API_BASE_URL` 默认 `http://localhost:8000`
- `AGENT_MAX_DEPTH` 默认 `10`
- `AGENT_MAX_NODES` 默认 `200`
- `AGENT_ROUTE_TIMEOUT_MS` 默认 `8000`
- `AGENT_TOP_CANDIDATES` 默认 `3`
- `AGENT_DUPLICATE_EXPAND_LIMIT` 默认 `3`
