# AI 接手上下文 — 幻兽帕鲁配种 Agent

> 新 AI 会话开始时，先读这个文件即可快速理解项目全貌。

---

## 一句话描述

一个智能化的**幻兽帕鲁（Palworld）配种助手 Agent**。用户输入帕鲁名或"工种:等级"，系统通过 ORM 查询服务访问 PostgreSQL 计算 CombiRank 配种公式，返回所有可能的父母组合。

---

## 核心概念

| 术语 | 含义 |
|------|------|
| **CombiRank** | 官方繁殖力值，配种计算唯一核心参数。子代 = 父母 CombiRank 平均值取最近 |
| **基础帕鲁** | `is_wild=true` 的帕鲁，野外可直接捕获 |
| **配种公式** | SQL: `round((a.combi_rank + b.combi_rank) / 2) = child.combi_rank` |
| **查询方式** | PostgreSQL 5 表规范化，CROSS JOIN + breeding_rule 守卫查询（无 JSON fallback） |

---

## 项目结构速览

```
pl-agent/
├── .github/              ← AI 行为指引
│   └── copilot-instructions.md
├── docs/
│   ├── architecture/     ← 架构与需求文档
│   │   ├── API_REQUIREMENTS.md
│   │   ├── ARCHITECTURE.md
│   │   ├── CORE_ENGINE_REQUIREMENTS.md (已归档)
│   │   ├── DATA_LAYER_REQUIREMENTS.md
│   │   ├── DATABASE_DESIGN.md
│   │   ├── MIGRATION_PLAN.md
│   │   └── PROJECT_STRUCTURE.md
│   ├── context/          ← AI 接手上下文
│   │   └── CONTEXT.md
│   └── decisions/        ← 设计决策记录
│
├── packages/
│   ├── core/             ← 📐 数据模型 (Python)
│   │   └── pl_agent/core/
│   │       ├── schema.py           ← ★ canonical models
│   │       ├── errors.py           ← domain exceptions
│   │       ├── data_loader.py      ← 离线数据工具（API 运行时不使用）
│   │       └── __tests__/          ← 数据模型测试
│   ├── adapters/         ← 🔌 外部数据适配
│   │   └── adapters/
│   │       ├── base.py             ← Adapter 抽象
│   │       ├── validator.py        ← 数据校验
│   │       ├── paldb/              ← paldb.cc 适配器
│   │       │   ├── scraper.py      ← HTML 爬虫
│   │       │   ├── parser.py       ← HTML 解析
│   │       │   ├── adapter.py      ← 数据适配
│   │       │   └── __tests__/      ← 解析器测试 (5)
│   │       ├── postgres/           ← PostgreSQL 适配器
│   │       │   ├── adapter.py      ← Pal → PG 写入
│   │       │   └── loader.py       ← PG → 内存加载
│   │       └── gamefile/           ← 游戏文件 (预留)
│   ├── api/              ← 🌐 FastAPI + 业务逻辑
│   │   └── pl_agent/api/
│   │       ├── db/                 ← SQLAlchemy Async ORM 层
│   │       ├── main.py             ← FastAPI 入口 + lifespan
│   │       ├── parser.py           ← 输入解析 (NAME/SUITABILITY/FUZZY)
│   │       ├── formatter.py        ← 响应格式化
│   │       ├── routes/
│   │       │   └── query.py        ← 路由 + ORM 查询调用
│   │       └── __tests__/          ← API 测试
│   ├── agent/            ← 🤖 独立 agent 模块 (Python, 无 web 依赖)
│   │   └── pl_agent/agent/
│   │       ├── llm/                ← LLM 客户端抽象 (DeepSeek/OpenAI 兼容)
│   │       ├── tools/              ← function calling 工具 (配种/解析/统计)
│   │       ├── memory/             ← 长期记忆 (file/postgres) + 上下文压缩
│   │       ├── graph/              ← AgentWorkflow / AgentLoop / guards
│   │       ├── intent/             ← 意图识别 (LLM + 规则回退)
│   │       ├── interaction/        ← 响应构建 / 点击协议
│   │       ├── state/              ← 会话状态模型 + 内存仓库
│   │       ├── auth/               ← 用户存储/密码/token (无路由)
│   │       ├── clients/            ← breeding API client
│   │       ├── summarizer/         ← 配种树摘要
│   │       └── config.py           ← 运行时配置 + .env 加载
│   ├── agent-web/        ← 🌐 agent 的 FastAPI 服务层 (服务前端)
│   │   └── pl_agent/agent_web/
│   │       ├── app.py              ← FastAPI 入口 + lifespan + 路由
│   │       └── auth/routes.py      ← /auth/register|login|me
│   ├── nlu/              ← 💬 意图解析 (v0.2)
│   └── web/              ← 🖥️ 前端 UI (v0.3)
│
├── data/                 ← 📊 数据文件
│   ├── raw/
│   ├── processed/
│   ├── sql/              ←   PostgreSQL DDL/迁移
│   │   ├── 001_create_pals.sql   ← 旧宽表 (已被 002 替代)
│   │   └── 002_normalize.sql    ← 5 表规范化 ⭐
│   └── archive/
├── tests/                ← 🧪 集成/冒烟测试
│   └── smoke/
│       └── test_breeding_smoke.py  ← 6 端到端场景
├── Makefile              ← 常用命令 (make serve/test/scrape...)
├── pyproject.toml        ← uv workspace monorepo
└── README.md
```

---

## 数据流

```
v0.3 (当前):  paldb.cc → scraper → parser → adapter → PostgreSQL (5 表)
                                                         │
                                          ┌──────────────┴──────────────────┐
                                          ▼                                 ▼
                                    API 启动加载                        API 运行时
                                    ORM load_all_pals                 ORM 查询 (CROSS JOIN)
                                    (selectinload 拼装 Pal)           + breeding_rule 守卫
                                                                      属性筛选 (参数化 JOIN)
                                                                      统计 (GROUP BY)
```

---

## Agent 架构（packages/agent + packages/agent-web）

```
前端 (React, packages/web) ──HTTP──▶ agent-web (FastAPI, :9000)
                                        │
                              app.py lifespan 装配：
                              user_store / long_term_memory / LLM / workflow
                                        ▼
                                   AgentWorkflow
                          ┌──────────────┼──────────────┐
                          ▼              ▼              ▼
                    短期记忆        长期记忆        上下文压缩
                 (chat_history)   (用户持久事实)   (LLM 摘要)
                          │              │              │
                          └──────────────┼──────────────┘
                                         ▼
                                    AgentLoop
                          (LLM function calling 多轮循环)
                                         │
                          ┌──────────────┼──────────────┐
                          ▼              ▼              ▼
                     ToolRegistry   DeepSeekClient   BreedingApiClient
                     (配种工具)      (pl_agent.llm)   (上游 :8000)
```

**关键组件**：
- `agent-web/app.py`：FastAPI 入口，lifespan 装配各组件；路由 `/agent/chat` `/agent/action` `/agent/session/{id}` `/auth/*`
- `agent/graph/workflow.py`：`AgentWorkflow` 主编排（配种必须调工具、省略主语结合上下文推断等行为规则）
- `agent/prompts/`：**所有 LLM 提示词集中存放**（独立 `.md` 文件，便于阅读与优化）——`assistant.md`（主助手）/ `intent_recognizer.md`（意图识别）/ `context_compress.md`（对话压缩）；由 `prompts/__init__.py` 用 `importlib.resources` 加载导出
- `agent/graph/agent_loop.py`：`AgentLoop` 多轮 tool_calls 循环，透传 wire-format dict 消息
- `agent/tools/breeding.py`：确定性配种工具（query_parent_pairs / resolve_pal / query_top_suitability / query_pal_stats）
- `agent/llm/`：可插拔 LLM 抽象（`LLMClient`），`DeepSeekClient` 走 OpenAI 兼容协议
- `agent/memory/`：`LongTermMemory`（file）`PostgresLongTermMemory`（PG）+ `compress.py` 摘要压缩
- `agent/auth/`：用户核心（存储/密码/token，**无 FastAPI 路由**）；路由在 `agent-web/auth/routes.py`

**依赖方向**：`agent-web` → `agent`（workspace）；`agent` 不依赖 FastAPI。

---

## 记忆系统

### 短期记忆（会话内）
- `SessionState.chat_history` 记录最近 `SHORT_TERM_MAX_TURNS`（默认 12）轮 user+assistant
- 前端 `useAgentSession` 用 localStorage 持久化 sessionId（`pl_agent_session_id`），页面刷新保持同一会话
- ⚠️ 会话状态目前存内存（`InMemorySessionRepository`），**服务重启会丢失**；未来可做 Postgres 会话仓库

### 长期记忆（跨会话持久）
- 存储用户持久事实（"用户拥有阿努比斯"、"用户偏好墨罗娜"），**按用户维度隔离**
- 存储后端：`LONG_TERM_STORE=file`（`packages/agent/data/`）或 `postgres`（`agent_long_term_memory` 表）
- 事实抽取：规则式正则（`extract_owned_facts` / `extract_preference_facts`），识别"我已有/我喜欢 帕鲁名"

### 上下文压缩
- 短期记忆超过 `max_turns*2` 时，最早一批对话用 LLM 压缩成摘要（`memory/compress.py`）
- 摘要存 `SessionState.history_summary`，每轮注入 system prompt

### 用户体系
- `POST /auth/register` `POST /auth/login` 返回 HMAC 签名 token（`AUTH_SECRET`）
- chat/action 带 `Authorization: Bearer <token>` 时按用户隔离长期记忆；匿名回退 `default_user_key`
- 用户存储：`USER_STORE=file`（`packages/agent/data/users.json`）或 `postgres`（`agent_users` 表）
- 密码 PBKDF2-HMAC-SHA256 哈希（`agent/auth/security.py`）

---

## 数据来源

**主力**: [paldb.cc](https://paldb.cc/cn/) — 活跃维护 (v1.0.2, 2026-07-29)，中文，服务端渲染 HTML，可爬取。

**关键字段** (从 paldb.cc HTML 提取):

| 字段 | HTML 定位 | 用途 |
|------|----------|------|
| `CombiRank` | `CombiRank {数值}` | 配种计算 |
| 工作适应性 | `{工种} Lv{等级}` | 属性反向查询 |
| `ZukanIndex` | `{中文名} #{编号}` | 唯一编号 |
| `ElementType1` | `ElementType1 {属性}` | 属性分类 |
| `Rarity` | `Rarity {数值}` | 稀有度 |

**备选**: 游戏文件解包 (FModel 导出 DT_PalCombiRank.uasset 等)

---

## 当前开发状态

| 阶段 | 状态 | 产出 |
|------|:---:|------|
| 架构设计 | ✅ | `docs/architecture/*` |
| Schema 定义 | ✅ | `schema.py` — Pal, WorkSuitability, PalRow, BreedingRuleRow |
| 数据层 | ✅ | scraper → parser → adapter → PostgreSQL (5 表) |
| API 服务 | ✅ | FastAPI — SQLAlchemy Async ORM, 参数化查询, 8 端点 |
| Agent 服务 | ✅ | `packages/agent/`（独立 agent 模块）+ `packages/agent-web/`（FastAPI 服务层）— chat/action/session 接口、LLM function calling、记忆系统、用户体系、测试体系 |
| 数据库规范化 | ✅ | 5 表 (pal/pal_element/work_suitability/pal_aliase/breeding_rule) |
| 测试 | ✅ | ORM 单测 7/7 + API 冒烟 8/8 通过 |
| Makefile | ✅ | 统一入口已包含 `serve-agent-service` / `test-agent` / `test-agent-web` |
| NLU 模块 | ⏭️ | 跳过, 结构化输入 |
| 前端 UI | ✅ | `packages/web/` — React + Vite 聊天交互页，已接入 agent-web |

## API 端点一览

| 端点 | 方法 | 说明 |
|------|:---:|------|
| `/health` | GET | 健康检查, 返回 pals_loaded |
| `/api/query` | POST | **智能查询** — 自动判断输入类型 |
| `/api/pal/{id}` | GET | 帕鲁详情 |
| `/api/breeding/tree/{id}` | GET | 父母对列表 (一级) |
| `/api/suitability/stats` | GET | 全工种统计 |

API 运行约束：
- PostgreSQL 为必需依赖；数据库不可用时 API 启动失败，不会回退到 JSON。

## Agent-web 端点一览

| 端点 | 方法 | 说明 |
|------|:---:|------|
| `/health` | GET | 健康检查 |
| `/agent/chat` | POST | 聊天入口（LLM + function calling，含短期/长期记忆、上下文压缩） |
| `/agent/action` | POST | 动作入口（confirm_target / expand_parent / select_parent_pair） |
| `/agent/session/{session_id}` | GET | 会话快照读取 |
| `/auth/register` | POST | 用户注册（返回 token） |
| `/auth/login` | POST | 用户登录（返回 token） |
| `/auth/me` | GET | 当前用户（Bearer token） |

**启动**:
- `make serve` → http://localhost:8000
- `make serve-agent-service` → http://localhost:9000

**测试**:
- `make test-agent`（agent 模块单元测试）
- `make test-agent-web`（agent-web 服务测试）
- `make test-web`（web 构建校验）
- `make test-all`（根项目 + agent + agent-web）

**输入示例**:
- `{"input": "阿努比斯"}` → 父母对列表
- `{"input": "手工:4"}` → 工作适应性筛选
- `{"input": "手工:6"}` → 超范围自动回退展示最优

## 下一步

| 优先级 | 任务 | 位置 |
|:---:|------|------|
| 1 | 前端登录注册页面 | `packages/web/`（后端已就绪） |
| 2 | Agent 服务会话存储从内存升级到 Redis | `packages/agent/pl_agent/agent/state/` |
| 3 | NLU 模块增强与多工种意图扩展 | `packages/nlu/` |
| 4 | 特殊配种规则扩充 | `packages/api/pl_agent/api/routes/query.py` + `packages/api/pl_agent/api/db/queries.py` |

详细设计见 `docs/architecture/` 下各需求文档。

---

## 技术栈

- **后端**: Python 3.10+ / FastAPI
- **前端**: TypeScript / React 18 / Vite
- **数据库**: PostgreSQL 16 + SQLAlchemy Async ORM + asyncpg
- **语音**: Web Speech API (MVP) → Whisper (进阶)
- **NLU**: 规则引擎 (MVP) → LLM (进阶)

---

## 配种算法

```sql
-- Step 0: 查特殊规则 (unbreedable/same_species/fixed_pair)
SELECT br.rule_type, br.parent_a_id, br.parent_b_id
FROM breeding_rule br JOIN pal p ON br.child_id = p.id
WHERE p.game_id = $target_game_id;

-- Step 1: CombiRank 公式 (无特殊规则时)
SELECT a.cn_name, b.cn_name, a.combi_rank, b.combi_rank
FROM pal a, pal b
WHERE round((a.combi_rank + b.combi_rank) / 2.0) = $target_rank
  AND a.game_id != $target_game_id AND b.game_id != $target_game_id
  AND a.id <= b.id;
```

两步流程: 先查 breeding_rule 守卫 (unbreedable 直接返回空)，再走 CROSS JOIN。
返回一级父母对，点击继续查。无递归 BFS。

---

## 架构要点

- **core 包**: 纯数据模型，含 PalRow/BreedingRuleRow DB 行类型，无业务逻辑
- **api 包**: 业务逻辑在路由层，数据库访问集中在 ORM 查询服务，两步配种查询 (守卫 + CROSS JOIN)
- **数据库**: 5 表规范化 (pal/pal_element/work_suitability/pal_aliase/breeding_rule)
- **属性筛选**: 参数化 JOIN work_suitability，消除 SQL 注入
- **数据源策略**: API 仅使用 PostgreSQL，不启用 JSON 降级

---

## 文件快速索引

| 想看什么 | 去哪个文件 |
|---------|-----------|
| 为什么这样设计 | `docs/architecture/ARCHITECTURE.md` |
| 目录怎么组织的 | `docs/architecture/PROJECT_STRUCTURE.md` |
| 🔑 数据模型规范 (Schema) | `packages/core/pl_agent/core/schema.py` |
| 🔑 数据层详细需求 | `docs/architecture/DATA_LAYER_REQUIREMENTS.md` |
| 🗄️ 数据库设计 (ERD/DDL) | `docs/architecture/DATABASE_DESIGN.md` |
| 🔌 外部数据如何接入 | `packages/adapters/base.py` + `docs/architecture/DATA_LAYER_REQUIREMENTS.md` |
| 🌐 API 服务需求 | `docs/architecture/API_REQUIREMENTS.md` |
| ⚙️ 配种逻辑实现 | `packages/api/pl_agent/api/routes/query.py` + `packages/api/pl_agent/api/db/queries.py` |
| 🧪 ORM 单元测试 | `packages/api/pl_agent/api/__tests__/test_orm_queries.py` |
| ❗ 业务异常定义 | `packages/core/pl_agent/core/errors.py` |
| API 有哪些接口 | `docs/architecture/API_REQUIREMENTS.md` §3 |
| AI 行为指引 | `.github/copilot-instructions.md` |
| 数据库 DDL | `data/sql/002_normalize.sql` |
| 迁移计划 | `docs/architecture/MIGRATION_PLAN.md` |
| 初始需求 | `init.md` |
