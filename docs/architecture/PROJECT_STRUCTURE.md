# 项目目录结构

> 更新: 2026-07-31 | Monorepo + PostgreSQL | 热缓存/冷查询分层

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
│   │   ├── CORE_ENGINE_REQUIREMENTS.md
│   │   ├── DATA_LAYER_REQUIREMENTS.md
│   │   └── PROJECT_STRUCTURE.md
│   ├── context/
│   │   └── CONTEXT.md               ←   AI 接手上下文
│   └── decisions/                   ←   ADR 设计决策记录
│       └── 002-postgres-storage.md
│
├── packages/                         ← 📦 Monorepo 业务包
│   ├── core/                         ← 🧠 配种算法引擎 (Python)
│   │   ├── demo/engine_demo.py
│   │   └── pl_agent/core/
│   │       ├── schema.py             ← ★ canonical models
│   │       ├── errors.py             ← 领域异常
│   │       ├── interfaces.py         ← ABCs / Protocols
│   │       ├── breeding_engine.py    ← CombiRank 配种计算
│   │       ├── breeding_tree.py      ← BFS 配种树构建
│   │       ├── suitability_query.py  ← 工作适应性查询
│   │       ├── path_optimizer.py     ← 路径择优
│   │       ├── data_loader.py        ← JSON 加载 (降级用)
│   │       └── __tests__/            ← 12 单元测试
│   │
│   ├── adapters/                     ← 🔌 外部数据适配 (Python)
│   │   └── adapters/
│   │       ├── base.py               ← Adapter 抽象接口
│   │       ├── validator.py          ← 数据校验器
│   │       ├── paldb/                ← paldb.cc 适配器
│   │       │   ├── scraper.py        ← HTML 爬虫
│   │       │   ├── parser.py         ← HTML 解析
│   │       │   ├── adapter.py        ← 数据适配 + JSON 输出
│   │       │   ├── demo/run_scraper.py
│   │       │   └── __tests__/        ← 5 解析器测试
│   │       ├── postgres/             ← PostgreSQL 适配器 (v0.2)
│   │       │   ├── config.py         ← DATABASE_URL 配置
│   │       │   ├── adapter.py        ← Pal → PG 批量 UPSERT
│   │       │   └── loader.py         ← PG → BreedingIndex (热缓存)
│   │       └── gamefile/             ← 游戏文件适配 (预留)
│   │
│   ├── api/                          ← 🌐 FastAPI 服务 (Python)
│   │   └── pl_agent/api/
│   │       ├── __init__.py           ← QueryRequest 模型
│   │       ├── main.py               ← 入口 + lifespan (热缓存加载)
│   │       ├── parser.py             ← 输入解析 (NAME/SUITABILITY/FUZZY)
│   │       ├── formatter.py          ← 响应格式化
│   │       ├── routes/query.py       ← 8 端点路由
│   │       └── __tests__/            ← API 冒烟脚本
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
                    ┌──────────┴──────────┐
                    ▼                     ▼
              pal_data.json          PostgreSQL
              (兼容保留)              (主存储)
                    │                     │
                    │          ┌──────────┴──────────┐
                    │          ▼                     ▼
                    │    热缓存 (启动时)         冷查询 (运行时)
                    │    BreedingIndex            PG 直连
                    │    (~10KB 内存)             详情/统计/搜索
                    │          │                     │
                    └──────────┴─────────────────────┘
                               │
                               ▼
                          核心引擎 (纯算法)
                     BFS 配种树 / 属性查询 / 路径择优
                               │
                               ▼
                          API 网关 (FastAPI)
                               │
                               ▼
                          前端 UI (React)
```

| 边 | 方向 | 协议/方式 | 延迟 |
|----|------|----------|:---:|
| adapters → PG | Pal → SQL | asyncpg | ~1ms/条 |
| adapters → JSON | Pal → JSON | 文件写入 | 离线 |
| PG → BreedingIndex | SQL → 内存 dict | asyncpg 全量 SELECT | ~50ms 启动 |
| BreedingIndex → Engine | 内存 dict 查找 | Python `dict.get()` | ~50ns |
| PG → API 详情 | SQL 单行 | asyncpg | ~1ms |
| Engine → API | Python import | 同进程调用 | <1μs |
| API → Web | HTTP REST | JSON | ~10ms |

> **关键**: 配种引擎访问 BreedingIndex (内存) 而非 PG。BFS 反向搜索 O(n²) 次查找，内存 ~50ns/次 vs PG ~1ms/次，差 20,000 倍。

---

## 各包职责边界

### `packages/core` — 核心引擎

- **职责**: 纯算法，无 I/O 依赖
- **输入**: `BreedingIndex` (轻量索引) 或 `list[Pal]`
- **输出**: `BreedingTree`、候选 `Pal` 列表
- **不依赖**: adapters、api、nlu、web、数据库驱动
- **内含**: `schema.py` — 全项目唯一 canonical 数据规范

### `packages/adapters` — 外部数据适配

- **职责**: 对接外部数据源，统一转为 canonical 格式
- **子包**:
  - `paldb/`: paldb.cc 爬虫 (scraper → parser → adapter → JSON)
  - `postgres/`: PostgreSQL 适配 (adapter 写入 + loader 读取热缓存)
  - `gamefile/`: 游戏文件解包适配 (预留)
- **输出**: JSON 文件 + PostgreSQL 表
- **依赖**: `packages/core` (仅 import schema)

### `packages/api` — API 网关

- **职责**: HTTP 路由、输入解析、响应格式化、热缓存加载
- **lifespan**: 启动时从 PG 加载 BreedingIndex → 构建 Engine
- **依赖**: core (引擎) + adapters/postgres (加载)
- **框架**: FastAPI + asyncpg

### `packages/nlu` — 自然语言理解 (v0.2 预留)

- **职责**: 中文文本 → 结构化意图 + 实体
- **输入**: 用户原始文本
- **输出**: `Intent` + `ExtractedEntity`

### `packages/web` — 前端 UI (v0.3 预留)

- **职责**: 搜索交互、配种树可视化
- **依赖**: api (HTTP REST)
- **框架**: React 18 + Vite

### `packages/shared` — 跨包共享 (预留)

- **职责**: TypeScript 类型定义 (`Pal`, `BreedingTree` 等接口)
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
api/routes/query.py → suitability.query("handiwork", 4)
  │                    ↑ 从 BreedingIndex (内存) 查找
  │
  ▼
返回候选列表 → 用户选择 "阿努比斯"
  │
  ▼
POST /api/query {"input": "阿努比斯"}
  │
  ├── 名称匹配 → Pal (BreedingIndex)
  ├── breeding_tree.build(pal)
  │   └── BFS 反向搜索 (BreedingIndex, ~200K 次 O(1) 查找)
  ├── optimizer.optimize(tree)
  └── format_name_query(pal, tree) → JSON
  │
  ▼
返回配种树 (含 display_text)
```

**Pal 详情查询** (运行时 PG 冷查询):
```
GET /api/pal/anubis
  │
  ├── id/cn_name/rank → BreedingIndex (内存, 即取即用)
  └── image_url/wiki_url/spawn_locations → PG (按需查询)
```

---

## 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 包名 | 小写 + 下划线 | `pl_agent.core.breeding_engine` |
| Python 模块 | 小写 + 下划线 | `data_loader.py` |
| Python 类 | PascalCase | `BreedingTreeBuilder` |
| Python 函数 | snake_case | `build_breeding_tree()` |
| TypeScript 组件 | PascalCase | `SearchBox.tsx` |
| TypeScript 接口 | PascalCase + I 前缀(可选) | `Pal`, `BreedingPath` |
| JSON 字段 | snake_case | `combi_rank`, `cn_name` |
| 数据文件 | snake_case | `pal_data.json` |
