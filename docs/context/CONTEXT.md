# AI 接手上下文 — 幻兽帕鲁配种 Agent

> 新 AI 会话开始时，先读这个文件即可快速理解项目全貌。

---

## 一句话描述

一个智能化的**幻兽帕鲁（Palworld）配种助手 Agent**。用户用文字/语音描述目标帕鲁（如"手工10级的帕鲁"），系统返回从野外基础帕鲁开始的**完整配种树**。

---

## 核心概念

| 术语 | 含义 |
|------|------|
| **CombiRank** | 官方繁殖力值，配种计算唯一核心参数。子代 = 父母 CombiRank 平均值取最近 |
| **基础帕鲁** | `is_wild=true` 的帕鲁，野外可直接捕获，配种树的叶子节点 |
| **配种树** | 从基础帕鲁到目标帕鲁的完整配种链路，BFS 反向搜索 + 递归展开 |
| **工作适应性** | 12 种工作类型（手工、生火、采矿...），用户可按此反向查帕鲁 |

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
│   │   ├── CORE_ENGINE_REQUIREMENTS.md
│   │   ├── DATA_LAYER_REQUIREMENTS.md
│   │   └── PROJECT_STRUCTURE.md
│   ├── context/          ← AI 接手上下文
│   │   └── CONTEXT.md
│   └── decisions/        ← 设计决策记录
│
├── packages/
│   ├── core/             ← 🧠 配种算法引擎 (Python)
│   │   ├── demo/         ←    快速验证脚本
│   │   └── pl_agent/core/
│   │       ├── __init__.py
│   │       ├── schema.py           ← ★ canonical models
│   │       ├── errors.py           ← domain exceptions
│   │       ├── interfaces.py       ← ABCs / Protocols
│   │       ├── breeding_engine.py  ← CombiRank 配种计算
│   │       ├── breeding_tree.py    ← BFS 配种树构建
│   │       ├── suitability_query.py← 工作适应性查询
│   │       ├── path_optimizer.py   ← 路径择优
│   │       ├── data_loader.py      ← JSON 数据加载
│   │       └── __tests__/          ← 单元测试 (12)
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
│   ├── api/              ← 🌐 FastAPI 服务
│   │   └── pl_agent/api/
│   │       ├── __init__.py         ← QueryRequest 模型
│   │       ├── main.py             ← FastAPI 入口 + lifespan
│   │       ├── parser.py           ← 输入解析 (NAME/SUITABILITY/FUZZY)
│   │       ├── formatter.py        ← 响应格式化
│   │       ├── routes/
│   │       │   └── query.py        ← 所有 API 路由
│   │       └── __tests__/          ← API 冒烟测试
│   ├── nlu/              ← 💬 意图解析 (v0.2)
│   └── web/              ← 🖥️ 前端 UI (v0.3)
│
├── data/                 ← 📊 数据文件
│   ├── raw/
│   ├── processed/
│   ├── sql/              ←   PostgreSQL 迁移脚本
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
v0.1 (当前):  paldb.cc → scraper → parser → adapter → pal_data.json → DataLoader → Engine

v0.2 (计划):  paldb.cc → scraper → parser → adapter → PostgreSQL
                                                         │
                                          ┌──────────────┴──────────────┐
                                          ▼                             ▼
                                    热缓存 (启动)                   冷查询 (运行时)
                                    id/combi_rank                 详情/统计/搜索
                                    is_wild/work_suit              PG 直连
                                          │
                                          ▼
                                       Engine (BFS 配种树)
```

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
| Schema 定义 | ✅ | `schema.py` — Pal, WorkSuitability, Element, WorkType, BreedingRules |
| 错误处理 | ✅ | `errors.py` — 6 种领域异常 |
| 组件接口 | ✅ | `interfaces.py` — 5 个 Protocol |
| 数据层 | ✅ | scraper → parser → adapter → validator |
| 核心引擎 | ✅ | breeding_engine + breeding_tree + suitability_query + path_optimizer |
| 数据加载器 | ✅ | `data_loader.py` — JSON 多索引加载 |
| PostgreSQL 存储 | 📝 | `adapters/postgres/` — 方案已定，待实现 |
| API 服务 | ✅ | FastAPI — 8 端点, lifespan 启动, CORS |
| 单元测试 | ✅ | 23 pytest (12 引擎 + 5 数据 + 6 冒烟) |
| Makefile | ✅ | make serve / test / scrape / demo / lint / format |
| NLU 模块 | ⏭️ | 跳过 v0.1, 直接用结构化输入 |
| 前端 UI | ⬜ | `packages/web/` — v0.3 计划 |

## API 端点一览

| 端点 | 方法 | 说明 |
|------|:---:|------|
| `/health` | GET | 健康检查, 返回 pals_loaded |
| `/api/query` | POST | **智能查询** — 自动判断输入类型 |
| `/api/pal/{id}` | GET | 帕鲁详情 |
| `/api/breeding/tree/{id}` | GET | 配种树 (可选 `?all=true&max_depth=5`) |
| `/api/suitability/stats` | GET | 全工种统计 |

**启动**: `make serve` → http://localhost:8000

**输入示例**:
- `{"input": "阿努比斯"}` → 配种树查询
- `{"input": "手工:4"}` → 工作适应性筛选
- `{"input": "手工:6"}` → 超范围自动回退展示最优

## 下一步

| 优先级 | 任务 | 位置 |
|:---:|------|------|
| 1 | PostgreSQL 存储迁移 | `packages/adapters/adapters/postgres/` |
| 2 | 从 paldb.cc 抓取完整数据 | `make scrape` |
| 3 | 编写 API 集成测试 | `packages/api/pl_agent/api/__tests__/` |
| 4 | NLU 模块（模糊匹配增强） | `packages/nlu/` |
| 5 | 前端 UI | `packages/web/` |

详细设计见 `docs/architecture/` 下各需求文档。

---

## 技术栈

- **后端**: Python 3.10+ / FastAPI
- **前端**: TypeScript / React 18 / Vite
- **数据库**: PostgreSQL 16 + asyncpg (v0.2 迁移目标)
- **数据**: JSON 文件 (当前) → PostgreSQL (计划)
- **语音**: Web Speech API (MVP) → Whisper (进阶)
- **NLU**: 规则引擎 (MVP) → LLM (进阶)

---

## 关键算法参考

- **配种公式**: `child_rank = round((a.combi_rank + b.combi_rank) / 2)`，取最接近 CombiRank 的帕鲁
- **特殊规则**: 传说帕鲁同类繁殖、部分亚种固定父母组合、Boss 帕鲁不可配种
- **配种树**: BFS 反向搜索，visited 防循环，max_depth=5，按步数择优

参考项目: [azmiao/PalWorldPlugin](https://github.com/azmiao/PalWorldPlugin) (Python 配种算法，但数据已过期)

---

## 命名空间包架构 (重要!)

`pl_agent` 是跨多包的 **PEP 420 命名空间包**。`core` 和 `api` 各自通过 `pkgutil.extend_path` 贡献子包:

```
packages/core/pl_agent/__init__.py   →  pkgutil.extend_path
packages/api/pl_agent/__init__.py    →  pkgutil.extend_path
```

- `import pl_agent` → 合并两个路径
- `from pl_agent.core.schema import Pal` → 来自 core
- `from pl_agent.api.main import app` → 来自 api

所有包的 `pl_agent/__init__.py` 必须保持 `extend_path` 模板。不要在顶层 `__init__.py` 中放业务代码。

---

## 文件快速索引

| 想看什么 | 去哪个文件 |
|---------|-----------|
| 为什么这样设计 | `docs/architecture/ARCHITECTURE.md` |
| 目录怎么组织的 | `docs/architecture/PROJECT_STRUCTURE.md` |
| 🔑 数据模型规范 (Schema) | `packages/core/pl_agent/core/schema.py` |
| 🔑 数据层详细需求 | `docs/architecture/DATA_LAYER_REQUIREMENTS.md` |
| �️ PostgreSQL 存储方案 | `docs/decisions/002-postgres-storage.md` |
| 🔌 外部数据如何接入 | `packages/adapters/base.py` + `docs/architecture/DATA_LAYER_REQUIREMENTS.md` |
| 🔑 核心引擎需求 | `docs/architecture/CORE_ENGINE_REQUIREMENTS.md` |
| 🌐 API 服务需求 | `docs/architecture/API_REQUIREMENTS.md` |
| ❗ 业务异常定义 | `packages/core/pl_agent/core/errors.py` |
| 🔧 引擎组件接口 | `packages/core/pl_agent/core/interfaces.py` |
| 配种算法怎么算 | `docs/architecture/CORE_ENGINE_REQUIREMENTS.md` §3 |
| API 有哪些接口 | `docs/architecture/API_REQUIREMENTS.md` §3 |
| AI 行为指引 | `.github/copilot-instructions.md` |
| 初始需求 | `init.md` |
