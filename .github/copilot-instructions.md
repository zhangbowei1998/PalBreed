# Copilot 行为指引 — pl-agent

## 项目背景

这是一个**幻兽帕鲁配种 Agent** 项目，帮助玩家找到最优配种路径。
每次新会话开始时，请先阅读 `docs/context/CONTEXT.md`。

## 架构规则

- **唯一 Schema**: 所有数据模型必须使用 `packages/core/pl_agent/core/schema.py` 中的规范定义。禁止在项目中定义重复的数据类型。
- **数据库**: 5 表规范化设计 (`docs/architecture/DATABASE_DESIGN.md`)，SERIAL PK + game_id UK
- **适配器层**: 外部数据必须通过 `packages/adapters/` 中的适配器流入
- **禁止循环引用**: `core` → 无依赖，`adapters` → 仅依赖 `core`，`api` → 依赖 `core`
- **Agent 模块**: `packages/agent`（纯逻辑，无 FastAPI）→ `packages/agent-web`（FastAPI 服务层）→ 依赖 `agent`。`agent` 不依赖 FastAPI/uvicorn。
- **命名空间**: 所有包挂在 PEP 420 命名空间 `pl_agent.*` 下（`pl_agent.core` / `pl_agent.agent` / `pl_agent.agent_web`）。
- **记忆/用户体系**: 见 `docs/context/CONTEXT.md` 的「记忆系统」与「用户体系」章节。

## 代码组织

- **单元测试**: 放在源码同目录的 `__tests__/` 下。命名规范: `test_*.py`。
- **集成测试**: 放在 `tests/integration/` 下，跨包联调测试。
- **冒烟测试**: 放在 `tests/smoke/` 下，核心流程端到端验证。
- **Demo 脚本**: 放在各包的 `demo/` 目录下，用于快速手动验证。
- **文档**: 按类型放在 `docs/architecture/`、`docs/context/`、`docs/decisions/` 下。
- **测试命令**: `make test-agent`（agent 单元）/ `make test-agent-web`（agent-web 服务）/ `make test-all`（全量）。

## Agent 模块约定

- **配种数据必须走工具**: Agent 逻辑（LLM）绝对不自行推算配种，必须调用 `packages/agent/pl_agent/agent/tools/breeding.py` 的工具。
- **LLM 抽象**: 业务代码只依赖 `pl_agent.agent.llm.LLMClient` 抽象，通过 `create_llm_client()` 创建（DeepSeek/OpenAI 兼容）。新增模型 → 实现 `LLMClient` 并注册到 factory。
- **记忆系统**:
  - 短期记忆: `SessionState.chat_history`（内存，重启丢失；上限 `SHORT_TERM_MAX_TURNS`）
  - 长期记忆: `pl_agent.agent.memory` 存储协议 `LongTermMemoryStore`（file / postgres 两种实现），**按用户维度隔离**
  - 上下文压缩: `memory/compress.py` 用 LLM 压缩早期对话到 `history_summary`
- **用户体系**: 认证核心在 `agent/auth/`（存储/密码/token，无路由）；FastAPI 路由在 `agent-web/auth/routes.py`。密钥来自 `AUTH_SECRET` 环境变量，**禁止硬编码密钥**。
- **配置**: `agent/config.py` 的 `Settings` 从 `.env` 读取（`packages/agent/.env`，已被 gitignore）。

## 错误处理

- 使用 `pl_agent.core.errors` 中定义的异常类处理所有业务异常。
- 业务代码禁止抛出泛型 `Exception` 或 `ValueError`。
- 映射关系:
  - 适配器错误 → `AdapterError`
  - 数据校验错误 → `DataIntegrityError`
  - 配种问题 → `BreedingLoopError` / `PalNotFoundError`
- Agent 内部: 工具执行错误 → `ToolError`；LLM 网络/解析错误 → `LLMError` 子类；状态冲突 → `StateConflictError` / `GuardViolation`。

## 数据来源

- 主数据源: [paldb.cc](https://paldb.cc/cn/) — 服务端渲染 HTML，可爬取解析。
- 配种公式: `子代 = 最接近 round((父A.CombiRank + 父B.CombiRank) / 2) 的帕鲁`
- 工作适应性: 12 种类型，等级范围 0-10（不设硬上限）。

## 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 模块 | `snake_case` | `routes/query.py` |
| Python 类 | `PascalCase` | `PostgresLoader` |
| Python 函数 | `snake_case` | `load_all()` |
| JSON 字段 | `snake_case` | `combi_rank` |
| 测试文件 | `test_*.py` | `test_api_smoke.py` |
| 测试函数 | `test_功能描述` | `test_smart_query_name` |

## 修改代码前

1. 先读 `docs/context/CONTEXT.md` 了解项目全貌
2. 查看 `docs/architecture/DATABASE_DESIGN.md` 了解 5 表规范化设计
3. 确认改动符合 `docs/architecture/PROJECT_STRUCTURE.md` 中的目录规范
4. 新增数据字段 → 先改 `schema.py`，再改 adapter/loader，最后改 routes/query.py
5. 修改数据库 → 更新 `data/sql/002_normalize.sql` + `DATABASE_DESIGN.md`

## 数据流

```
paldb.cc → adapters/paldb/scraper.py → parser.py → adapter.py → schema.Pal
                                                                      │
                                          ┌───────────────────────────┘
                                          ▼
                              adapters/postgres/adapter.py
                              (4 表事务: pal + element + aliase + work)
                                          │
                                          ▼
                                    PostgreSQL 16
                              (5 表: pal/pal_element/
                               work_suitability/pal_aliase/
                               breeding_rule)
                                          │
                              adapters/postgres/loader.py
                              (LOAD_ALL_SQL: 4 表 JOIN 拼装)
                                          │
                                          ▼
                              api/routes/query.py (SQL 直连)
```

任何新增数据源都走同样的 adapter 模式，不允许裸调外部 API 进入 core。

**Agent 数据流**（用户对话 → 配种结果）:
```
用户聊天 → agent-web (FastAPI :9000)
        → AgentWorkflow (graph/workflow.py)
        → AgentLoop (LLM function calling, graph/agent_loop.py)
        → ToolRegistry → breeding.py 工具 → BreedingApiClient (上游 api :8000)
        → 精确配种数据 → LLM 组织中文回答 → 前端
```

1. Read `docs/context/CONTEXT.md`
2. Check `docs/architecture/` for relevant design docs
3. Ensure changes align with the monorepo structure in `docs/architecture/PROJECT_STRUCTURE.md`
