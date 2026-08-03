# AI 接手上下文 — 幻兽帕鲁配种 Agent

> 版本: v0.1.0 | 更新: 2026-08-02
> 新 AI 会话开始时，先读这个文件即可快速理解项目全貌。
> 📖 文档分类导航见 [`docs/README.md`](../README.md)（总索引）。

---

## 一句话描述

一个智能化的**幻兽帕鲁（Palworld）配种助手 Agent**。用户输入帕鲁名或"工种:等级"，系统通过 ORM 查询服务访问 PostgreSQL 计算 CombiRank 配种公式，返回所有可能的父母组合。

---

## 核心概念

| 术语 | 含义 |
|------|------|
| **CombiRank** | 官方繁殖力值。子代 = rank 最接近 avg(父母 rank 平均) 的 **可配种(breed_child=true)** 帕鲁 |
| **breed_child** | 是否可作为配种子代。False 的帕鲁（稀有/变种/传说）只能通过独特组合获得 |
| **基础帕鲁** | `is_wild=true` 的帕鲁，野外可直接捕获 |
| **配种公式** | avg=(a.rank+b.rank)/2 → 子代=最近的 breed_child=true 帕鲁；独特组合（breeding_rule）优先 |
| **查询方式** | PostgreSQL 5 表规范化，独特组合 + rank 独占区间查询（无 JSON fallback） |

---

## 项目结构速览

```
pl-agent/
├── .github/              ← AI 行为指引
│   └── copilot-instructions.md
├── docs/
│   ├── README.md         ← 📖 文档总索引（分类导航，先看这里）
│   ├── architecture/     ← 架构文档（按 设计/实现/计划/需求/部署/归档 分子目录）
│   │   ├── design/       ←   现状设计（active）
│   │   │   ├── PROJECT_STRUCTURE.md
│   │   │   ├── DATABASE_DESIGN.md        ← v1.1 基础 5 表（历史基础版）
│   │   │   ├── DATABASE_DESIGN_TCIMBA_V2.md ← v2.0 全量 22 表（现状核心）
│   │   │   └── API_REQUIREMENTS.md
│   │   ├── agent/        ←   Agent 实现专项（01~10，最贴近代码）
│   │   ├── plans/        ←   开发计划（implemented）
│   │   │   ├── TCIMBA_DATA_DEVELOPMENT_PLAN.md
│   │   │   ├── TIER_IMPLEMENTATION_PLAN.md
│   │   │   ├── TEXT2SQL_PLAN.md + TEXT2SQL_EXECUTION_PLAN.md
│   │   │   └── MIGRATION_PLAN.md
│   │   ├── requirements/ ←   需求基线
│   │   ├── deploy/       ←   阿里云部署 + CI/CD
│   │   └── archive/      ←   已归档（archived，供历史溯源）
│   ├── context/          ← AI 接手上下文
│   │   ├── CONTEXT.md    ← ⭐ 唯一现状快照（SSOT）
│   │   ├── TCIMBA_DATA.md
│   │   └── Text-to-SQL.md
│   └── decisions/        ← 设计决策记录（ADR）
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
│   │       ├── tcimba/             ← tc-imba 数据源 (scripts/convert_tcimba.py)
│   │       │   ├── scraper.py      ← JSON 拉取
│   │       │   ├── parser.py       ← 字段映射
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
│   │   ├── 002_normalize.sql    ← 5 表规范化 ⭐
│   │   ├── 003_tcimba_extend.sql ← 17 扩展表 (22 表总)
│   │   └── 004_text2sql.sql     ← Text-to-SQL 宽表视图 (v_pal_full 等)
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
v0.4 (当前):  palworld.tc-imba.com → scripts/convert_tcimba.py → pal_data.json
            → seed (pal + breeding_rule 独特组合) → PostgreSQL (5 表)
                                                         │
                                          ┌──────────────┴──────────────────┐
                                          ▼                                 ▼
                                    API 启动加载                        API 运行时
                                    ORM load_all_pals                 ORM 查询 (独特组合
                                    (selectinload 拼装 Pal)           + rank 独占区间)
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

**主力**: [palworld.tc-imba.com](https://palworld.tc-imba.com/) — 玩家自建，**从游戏文件提取**，含完整帕鲁属性与配种数据（rank / breedChild / 独特组合）。不再使用 paldb.cc / palworld.gg。

**数据接口** (`data-palworld.tc-imba.com`) — **完整文件清单与结构见 [TCIMBA_DATA.md](./TCIMBA_DATA.md)**:

| 文件 | 内容 |
|------|------|
| `pals.json` | 帕鲁属性 (elements/rarity/work/stats/技能/掉落) |
| `breeding.json` | 配种: `pals[].rank + breedChild`、`combos[]` 独特组合 |
| `passives.json` | 被动技能 (含遗传 lotteryWeight) |
| `items.json` | 物品 (配方/来源/掉落) |
| `locales/zh-CN/pals.json` | 中文名 |
| `locales/zh-CN/passives.json` | 被动技能中文名 |
| `locales/zh-CN/skills.json` | 技能中文名+描述 |
| `locales/zh-CN/items.json` | 物品中文名+描述 |
| `locales/en-US/*.json` | 英文版同名文件 |

**配种规则**:
- `avg = (A.rank + B.rank) / 2`
- 子代 = rank 最接近 avg 的 `breed_child=true` 帕鲁（不可配种帕鲁不作为结果产出）
- `breed_child=false` 帕鲁只能通过独特组合（same_species / fixed_pair）获得

**22 表扩展（已实现）**:
- 数据库已扩展为 22 表（5 基础 + 帕鲁详情/技能/被动/物品/掉落/召唤），设计见 [DATABASE_DESIGN_TCIMBA_V2.md](../architecture/design/DATABASE_DESIGN_TCIMBA_V2.md)
- 导入: `scripts/fetch_tcimba.py`（抓取 13 文件）+ `scripts/validate_tcimba.py`（校验）+ `scripts/seed_tcimba_full.py`（幂等灌入 22 表，Docker entrypoint 使用）
- 适配器: `adapters/tcimba/`（parser/adapter → TciDataBundle）+ `adapters/postgres/ext_writer.py`
- 新查询: `queries.py` S6-S10（被动→帕鲁 / 技能 / 掉落反查 / 配方链 / 帕鲁详情）+ 端点 `/api/pals/{id}/detail` `/api/pals/{id}/skills` `/api/passives` `/api/items/{name}/recipe` `/api/items/{name}/drops`
- 开发计划: [TCIMBA_DATA_DEVELOPMENT_PLAN.md](../architecture/plans/TCIMBA_DATA_DEVELOPMENT_PLAN.md)

**三层接入（已实现，见 [TIER_IMPLEMENTATION_PLAN.md](../architecture/plans/TIER_IMPLEMENTATION_PLAN.md)）**:
- Agent 工具: `tools/pal_info.py` 新增 5 个（`query_pal_detail`/`query_pal_skills`/`query_pals_by_passive`/`query_item_drops`/`query_item_recipe`）+ `tools/sql_query.py` 1 个（`run_sql_query`），`build_breeding_tools` 共 10 个
- Agent client: `clients/breeding_api_client.py` 新增 5 方法（detail_full/skills/by_passive/recipe/drops）+ `run_sql_query`
- 提示词: `assistant.md` 规则 7 改为资源/物品走工具、规则 8 数据源改 tc-imba、新增规则 9（被动/技能/详情类）+ 工具优先级 + 数据库宽表 + 未收录拒绝规则
- data_cards: `interaction/presenter.build_data_cards` 从工具结果组装卡片 → `workflow.handle_chat` 注入 `data_cards` → agent-web 透传 → 前端 `components/DataCardList.tsx` 渲染（被动/掉落/配方/技能/详情摘要）

本地数据: `data/processed/pal_data.json`（由 `scripts/convert_tcimba.py` 从 tc-imba 生成）+ `data/tc-imba/`（原始数据）。

**备选**: 游戏文件解包 (FModel 导出 DT_PalCombiRank.uasset 等)

---

## 当前开发状态（v0.1.0）

| 阶段 | 状态 | 产出 |
|------|:---:|------|
| 架构设计 | ✅ | `docs/architecture/design/*`（现状）+ `archive/`（历史） |
| Schema 定义 | ✅ | `schema.py` — Pal, PalRow, WorkSuitability, BreedingRuleRow + 17 扩展模型 |
| 数据层 | ✅ | tc-imba 抓取/校验 → 22 表 (5 基础 + 17 扩展) |
| API 服务 | ✅ | FastAPI — SQLAlchemy Async ORM, 8 核心端点 + 5 tc-imba 扩展端点 + Text-to-SQL |
| Agent 服务 | ✅ | `packages/agent/` + `packages/agent-web/` — chat/action/session、LLM function calling、10 工具、记忆系统、用户体系 |
| Text-to-SQL | ✅ | `run_sql_query` 工具 + `/api/sql/query` 安全执行器（4 道防火墙） |
| 数据库规范化 | ✅ | 22 表 (pal/元素/工种/别名/配种规则 + stats/技能/被动/物品/掉落/召唤) |
| 测试 | ✅ | api 30 + agent 32 + agent-web 19 单测；冒烟 8/8 |
| Makefile | ✅ | `serve-agent-service` / `test-agent` / `test-agent-web` / `test-all` |
| NLU 模块 | ⏭️ | 跳过, 结构化输入 + LLM 意图识别 |
| 前端 UI | ✅ | `packages/web/` — React + Vite 聊天交互页，含配种树/数据卡片/导出 |
| 功能差距 | 📋 | 地图 / 科技树 / 属性模拟器 / 多代配种（见 `decisions/003-feature-gaps.md`） |

## API 端点一览

| 端点 | 方法 | 说明 |
|------|:---:|------|
| `/health` | GET | 健康检查 |
| `/api/query` | POST | **智能查询** — 自动判断输入类型 |
| `/api/pal/{id}` | GET | 帕鲁详情 |
| `/api/breeding/tree/{id}` | GET | 父母对列表 (一级) |
| `/api/suitability/stats` | GET | 全工种统计 |
| `/api/pals/{id}/detail` | GET | 帕鲁全量详情（tc-imba 扩展） |
| `/api/pals/{id}/skills` | GET | 帕鲁可学技能（tc-imba 扩展） |
| `/api/passives?name=` | GET | 按被动查帕鲁（tc-imba 扩展） |
| `/api/items/{name}/recipe` | GET | 物品配方（tc-imba 扩展） |
| `/api/items/{name}/drops` | GET | 物品掉落反查（tc-imba 扩展） |
| `/api/sql/query` | POST | Text-to-SQL 安全执行器 |

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

## 下一步（v0.1.0 → v0.2.0）

| 优先级 | 任务 | 位置 |
|:---:|------|------|
| 1 | **多代配种规划**（④，纯逻辑 BFS，收益最大） | `packages/api/` + `packages/agent/` |
| 2 | 前端登录注册页面 | `packages/web/`（后端已就绪） |
| 3 | **科技树**（②，新增表 + tc-imba 数据） | `packages/adapters/` + `data/sql/` |
| 4 | Agent 服务会话存储从内存升级到 Redis | `packages/agent/pl_agent/agent/state/` |
| 5 | **地图 / 属性模拟器**（①③） | 需额外数据源，见 `decisions/003-feature-gaps.md` |

详细差距与建议见 `docs/decisions/003-feature-gaps.md`；详细设计见 `docs/architecture/` 下各文档。

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
-- Step 0: 查独特组合 (same_species/fixed_pair) — breed_child=false 的帕鲁只能通过它获得
SELECT br.rule_type, br.parent_a_id, br.parent_b_id
FROM breeding_rule br JOIN pal p ON br.child_id = p.id
WHERE p.game_id = $target_game_id;

-- Step 1: CombiRank 独占区间 (只考虑 breed_child=true 的子代)
-- 子代 C 的独占区间: prev_rank + C.rank < A.rank + B.rank <= C.rank + next_rank
-- (prev/next 为 C 在 breed_child=true 帕鲁排序中的相邻 rank)
SELECT a.cn_name, b.cn_name, a.combi_rank, b.combi_rank
FROM pal a, pal b
WHERE a.combi_rank + b.combi_rank BETWEEN $sum_min AND $sum_max
  AND a.game_id != $target_game_id AND b.game_id != $target_game_id
  AND a.id <= b.id;
```

两步流程: 独特组合（same_species/fixed_pair）与 rank 公式结果合并返回；breed_child=false 的子代 rank 公式返回空。
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
| 📖 文档导航（总索引） | `docs/README.md` |
| 为什么这样设计 | `docs/architecture/archive/ARCHITECTURE.md`（历史）+ `docs/decisions/`（ADR） |
| 目录怎么组织的 | `docs/architecture/design/PROJECT_STRUCTURE.md` |
| 🔑 数据模型规范 (Schema) | `packages/core/pl_agent/core/schema.py` |
| 🗄️ 数据库设计 (22 表 ERD/DDL) | `docs/architecture/design/DATABASE_DESIGN_TCIMBA_V2.md` |
| 🗄️ 数据库基础 5 表 | `docs/architecture/design/DATABASE_DESIGN.md` |
| 🔌 外部数据如何接入 | `packages/adapters/` + `docs/context/TCIMBA_DATA.md` |
| 🌐 API 服务需求 | `docs/architecture/design/API_REQUIREMENTS.md` |
| ⚙️ 配种逻辑实现 | `packages/api/pl_agent/api/routes/query.py` + `packages/api/pl_agent/api/db/queries.py` |
| 🧪 ORM 单元测试 | `packages/api/pl_agent/api/__tests__/test_orm_queries.py` |
| ❗ 业务异常定义 | `packages/core/pl_agent/core/errors.py` |
| API 有哪些接口 | `docs/architecture/design/API_REQUIREMENTS.md` §3 |
| 🤖 Agent 实现说明 | `docs/architecture/agent/README.md`（01~10 包级） |
| AI 行为指引 | `.github/copilot-instructions.md` |
| 数据库 DDL | `data/sql/002_normalize.sql` + `003_tcimba_extend.sql` + `004_text2sql.sql` |
| 迁移计划 | `docs/architecture/plans/MIGRATION_PLAN.md` |
| 待开发功能差距 | `docs/decisions/003-feature-gaps.md` |
| 初始需求 | `init.md`（历史草稿） |
