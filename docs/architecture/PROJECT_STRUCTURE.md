# 项目目录结构

> 更新: 2026-08-01 | 5 表规范化 | ORM 配种查询

---

## 全景

```
pl-agent/
├── .github/                          ← AI 行为指引
│   └── copilot-instructions.md
│
├── docs/                             ← 📖 项目文档
│   ├── architecture/                 ←   架构与需求文档
│   │   ├── ARCHITECTURE.md
│   │   ├── API_REQUIREMENTS.md
│   │   ├── CORE_ENGINE_REQUIREMENTS.md (已归档)
│   │   ├── DATA_LAYER_REQUIREMENTS.md
│   │   ├── DATABASE_DESIGN.md       ← ★ 数据库 ERD + DDL (v1.1 基础 5 表)
│   │   ├── DATABASE_DESIGN_TCIMBA_V2.md ← ★ tc-imba 全量 22 表扩展设计
│   │   ├── TCIMBA_DATA_DEVELOPMENT_PLAN.md ← ★ tc-imba 数据接入开发计划 (P0-P7)
│   │   ├── MIGRATION_PLAN.md       ← 迁移开发计划
│   │   └── PROJECT_STRUCTURE.md
│   ├── context/
│   │   └── CONTEXT.md               ←   AI 接手上下文
│   └── decisions/                   ←   ADR 设计决策记录
│       └── 002-postgres-storage.md
│
├── packages/                         ← 📦 Monorepo 业务包
│   ├── core/                         ← 📐 数据模型 (Python)
│   │   └── pl_agent/core/
│   │       ├── schema.py             ← ★ canonical models
│   │       ├── errors.py             ← 领域异常
│   │       ├── data_loader.py        ← JSON 降级加载
│   │       └── __tests__/            ← 数据模型测试
│   │
│   ├── adapters/                     ← 🔌 外部数据适配 (Python)
│   │   └── adapters/
│   │       ├── base.py               ← Adapter 抽象接口
│   │       ├── validator.py          ← 数据校验器
│   │       ├── paldb/                ← paldb.cc 适配器（历史）
│   │       ├── tcimba/               ← tc-imba 适配器 (parser/adapter → TciDataBundle)
│   │       ├── postgres/             ← PostgreSQL 适配器
│   │       │   ├── config.py         ← DATABASE_URL 配置
│   │       │   ├── adapter.py        ← Pal → 5 表事务写入
│   │       │   ├── ext_writer.py     ← TciDataBundle → 22 表事务写入
│   │       │   └── loader.py         ← 4 表 JOIN 加载 + 参数化查询
│   │       └── gamefile/             ← 游戏文件适配 (预留)
│   │
│   ├── api/                          ← 🌐 FastAPI 服务 (Python)
│   │   └── pl_agent/api/
│   │       ├── __init__.py           ← QueryRequest 模型
│   │       ├── db/                   ← ORM 模型 + 查询服务
│   │       ├── main.py               ← 入口 + lifespan
│   │       ├── parser.py             ← 输入解析 (NAME/SUITABILITY/FUZZY)
│   │       ├── formatter.py          ← 响应格式化
│   │       ├── routes/query.py       ← 路由 + ORM 查询调用
│   │       └── __tests__/            ← API 冒烟脚本
│   │
│   ├── agent/                        ← 🤖 独立 agent 模块 (Python, 无 web 依赖)
│   │   └── pl_agent/agent/
│   │       ├── config.py             ← 运行时配置 + .env 加载
│   │       ├── llm/                  ← LLM 客户端抽象 (DeepSeek/OpenAI 兼容)
│   │       ├── tools/                ← function calling 工具 (配种/解析/统计)
│   │       ├── memory/               ← 长期记忆 (file/postgres) + 上下文压缩
│   │       ├── graph/                ← AgentWorkflow / AgentLoop / guards
│   │       ├── intent/               ← 意图识别 (LLM + 规则回退)
│   │       ├── interaction/          ← 响应构建 / 点击协议
│   │       ├── state/                ← 会话状态模型 + 内存仓库
│   │       ├── clients/              ← breeding API client
│   │       ├── auth/                 ← 用户存储/密码/token (无路由)
│   │       ├── summarizer/           ← 配种树摘要
│   │       ├── common/               ← 常量 / telemetry
│   │       ├── data/                 ← 本地数据 (file 模式记忆)
│   │       └── __tests__/            ← agent 单元测试
│   │
│   ├── agent-web/                    ← 🌐 agent 的 FastAPI 服务层 (服务前端)
│   │   └── pl_agent/agent_web/
│   │       ├── app.py                ← FastAPI 入口 + lifespan + 路由
│   │       └── auth/routes.py        ← /auth/register|login|me
│   │
│   ├── nlu/                          ← 💬 NLU 意图解析 (v0.2 预留)
│   └── web/                          ← 🖥️ 前端 UI (v0.3 预留)
│
├── data/                             ← 📊 数据文件
│   ├── raw/                          ←   爬虫原始 HTML
│   ├── processed/                    ←   构建产物 (pal_data.json)
│   ├── sql/                          ←   PostgreSQL DDL 迁移
│   │   └── 001_create_pals.sql
│   └── archive/                      ←   历史版本
│
├── tests/                            ← 🧪 测试
│   ├── smoke/                        ←   6 冒烟测试
│   └── integration/                  ←   集成测试 (预留)
│
├── pyproject.toml                    ← uv workspace 配置
├── Makefile                          ← make serve / test / scrape
├── init.md                           ← 初始需求草稿
└── README.md
```

---

## 包依赖关系

```
paldb.cc → scraper/parser → PalDBAdapter
                               │
                               ▼
                          PostgreSQL
                          (主存储)
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
             API 启动加载            API 运行时 ORM
             pals → 内存            配种查询 (CROSS JOIN)
             (Parser 索引)          属性筛选 (WHERE)
                    │                     │
                    └──────────┬──────────┘
                               │
                               ▼
                     FastAPI 路由 (API)
                               │
                               ▼
                          前端 UI (React)
```

| 边 | 方向 | 协议/方式 | 延迟 |
|----|------|----------|:---:|
| adapters → PG | Pal → SQL | asyncpg | ~1ms/条 |
| PG → API 启动 | ORM → 内存 | SQLAlchemy + asyncpg | ~50ms 启动 |
| PG → API 配种 | ORM CROSS JOIN | SQLAlchemy + asyncpg | ~10-50ms |
| PG → API 详情 | ORM SELECT | SQLAlchemy + asyncpg | ~1ms |
| API → Web | HTTP REST | JSON | ~10ms |

> 配种计算完全由 PostgreSQL 完成，利用数据库 CROSS JOIN 能力。

---

## 各包职责边界

### `packages/core` — 数据模型

- **职责**: 纯数据规范，无 I/O 依赖
- **内容**: `schema.py` (全项目唯一 canonical 规范) + `errors.py` (领域异常) + `data_loader.py` (JSON 降级)
- **不依赖**: adapters、api、nlu、web、数据库驱动

### `packages/adapters` — 外部数据适配

- **职责**: 对接外部数据源，统一转为 canonical 格式
- **子包**:
  - `paldb/`: paldb.cc 爬虫 (scraper → parser → adapter → JSON)
  - `postgres/`: PostgreSQL 适配 (adapter 写入 + loader 读取)
  - `gamefile/`: 游戏文件解包适配 (预留)
- **输出**: JSON 文件 + PostgreSQL 表
- **依赖**: `packages/core` (仅 import schema)

### `packages/api` — API + 业务逻辑

- **职责**: HTTP 路由、输入解析、ORM 配种查询、响应格式化
- **lifespan**: 启动时从 PG 加载 pals → 构建 Parser
- **依赖**: core (schema) + sqlalchemy + asyncpg
- **框架**: FastAPI + SQLAlchemy Async ORM

### `packages/agent` — 独立 agent 模块

- **职责**: LLM 对话 + function calling + 记忆系统 + 用户认证核心
- **包含**:
  - `llm/`: 可插拔 LLM 客户端抽象（DeepSeek / OpenAI 兼容）
  - `tools/`: 确定性配种工具（暴露给 LLM function calling）
  - `memory/`: 长期记忆（file/postgres）+ 短期记忆 + 上下文压缩
  - `graph/`: `AgentWorkflow` + `AgentLoop`（多轮 tool_calls）+ guards
  - `auth/`: 用户存储（file/postgres）、密码哈希、token 签发（**无 FastAPI 路由**）
  - `state/`: 会话状态模型 + 仓库
- **不依赖**: FastAPI / uvicorn（纯逻辑，可独立测试复用）
- **依赖**: httpx + pydantic + asyncpg + python-dotenv

### `packages/agent-web` — agent 的 FastAPI 服务层

- **职责**: 为前端提供 HTTP 服务
- **包含**:
  - `app.py`: FastAPI 入口 + lifespan 装配（用户存储/记忆/LLM/workflow）
  - `auth/routes.py`: `/auth/register` `/auth/login` `/auth/me`
- **依赖**: `packages/agent`（workspace）+ fastapi + uvicorn
- **框架**: FastAPI
- **端点**: `/health` `/agent/chat` `/agent/action` `/agent/session/{id}` + `/auth/*`

### `packages/nlu` — 自然语言理解 (v0.2 预留)

- **职责**: 中文文本 → 结构化意图 + 实体
- **输入**: 用户原始文本
- **输出**: `Intent` + `ExtractedEntity`

### `packages/web` — 前端 UI (v0.3 预留)

- **职责**: 搜索交互、配种结果可视化
- **依赖**: api (HTTP REST)
- **框架**: React 18 + Vite

### `packages/shared` — 跨包共享 (预留)

- **职责**: TypeScript 类型定义 (`Pal`, `ParentPair` 等接口)
- **被依赖**: web (类型引用)

---

## 数据流

```
用户输入 "手工:4"
  │
  ▼
POST /api/query {"input": "手工:4"}
  │
  ▼
api/parser.py → QueryKind.SUITABILITY
  │
  ▼
api/routes/query.py → ORM: work_suitability JOIN pal (handiwork >= 4)
  │
  ▼
返回候选列表 → 用户选择 "阿努比斯"
  │
  ▼
POST /api/query {"input": "阿努比斯"}
  │
  ├── 名称匹配 → Pal
  └── ORM 配种查询 (CROSS JOIN)
  │   select(pa.cn_name, pb.cn_name)
  │   where round((pa.combi_rank + pb.combi_rank) / 2.0) == rank
  └── format_name_query(pal, pairs) → JSON
  │
  ▼
返回父母对列表 (含 display_text)
```

**Pal 详情查询**:
```
GET /api/pal/anubis
  │
  └── PG: SELECT * FROM pals WHERE id = 'anubis'
```

---

## 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 包名 | 小写 + 下划线 | `pl_agent.api.routes.query` |
| Python 模块 | 小写 + 下划线 | `data_loader.py` |
| Python 类 | PascalCase | `QueryParser` |
| Python 函数 | snake_case | `format_breeding_result()` |
| TypeScript 组件 | PascalCase | `SearchBox.tsx` |
| TypeScript 接口 | PascalCase + I 前缀(可选) | `Pal`, `BreedingPath` |
| JSON 字段 | snake_case | `combi_rank`, `cn_name` |
| 数据文件 | snake_case | `pal_data.json` |
