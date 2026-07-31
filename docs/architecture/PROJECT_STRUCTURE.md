# 项目目录结构

> 更新: 2026-07-31 | Monorepo 架构

---

## 全景

```
pl-agent/
├── docs/                         # 📖 项目文档
│   ├── ARCHITECTURE.md           #    系统架构设计
│   ├── CONTEXT.md                #    AI 接手上下文
│   └── PROJECT_STRUCTURE.md      #    本文件 — 目录结构说明
│
├── packages/                     # 📦 Monorepo 业务包
│   ├── core/                     # 🧠 核心引擎 (Python)
│   │   └── pl_agent/core/        #    schema★ / data_loader / breeding_engine / breeding_tree / path_optimizer
│   │
│   ├── adapters/                 # 🔌 外部数据适配层 (Python)
│   │   ├── base.py               #    Adapter 抽象接口
│   │   ├── paldb/                #    paldb.cc 爬虫+解析+适配
│   │   ├── gamefile/             #    游戏文件解包适配
│   │   └── validator.py          #    数据校验器
│   │
│   ├── api/                      # 🌐 REST API 服务 (Python FastAPI)
│   │   └── pl_agent/api/routes/  #    breeding / query 路由
│   │
│   ├── nlu/                      # 💬 自然语言理解 (Python)
│   │   └── pl_agent/nlu/         #    intent_classifier / entity_extractor / disambiguator
│   │
│   ├── web/                      # 🖥️ 前端 UI (TypeScript + React/Vue)
│   │   ├── src/
│   │   │   ├── components/       #    UI 组件 (SearchBox, PalCard, BreedingTree, CandidateList)
│   │   │   ├── hooks/            #    React Hooks
│   │   │   ├── pages/            #    页面
│   │   │   └── services/         #    API 调用封装
│   │   └── public/               #    静态资源
│   │
│   └── shared/                   # 🔗 跨包共享 (TypeScript 类型定义 / 常量)
│
├── data/                         # 📊 数据文件 (版本化托管)
│   ├── raw/                      #    爬虫原始输出 (中间格式, 如 raw_pages/)
│   ├── processed/                #    加工后的正式数据 (pal_data.json, breeding_rules.json, zh_mapping.json)
│   └── archive/                  #    历史版本归档 (pal_data_v1.json, pal_data_v2.json ...)
│
├── scripts/                      # 🔧 离线工具 (不参与运行时)
│   ├── scraper/                  #    paldb.cc HTML 爬虫 (build_data.py, parser.py)
│   └── validator/                #    数据校验脚本 (check_consistency.py, diff_report.py)
│
├── tests/                        # 🧪 测试
│   ├── unit/                     #    单元测试 (每包独立测试)
│   ├── integration/              #    跨包集成测试
│   └── e2e/                      #    端到端测试
│
├── init.md                       # 原始需求草稿
├── pyproject.toml                # (待建) Python monorepo 配置
├── package.json                  # (待建) 前端 workspace 配置
└── README.md                     # (待建) 项目说明
```

---

## 包依赖关系

```
adapters (paldb/gamefile)  web (前端)
       │                      │
       ▼                      ▼
   canonical Schema ◀─── api (网关) ──▶ core (引擎) + nlu (NLU)
       │                      │                │
       ▼                      ▼                ▼
   data/processed/  ←──── 共享数据 ←── scripts/scraper → paldb.cc
```

| 边 | 方向 | 协议/方式 |
|----|------|----------|
| adapters → Schema | 数据转换 | Python import |
| web → api | HTTP REST | JSON |
| api → core | Python import | 同进程调用 |
| api → nlu | Python import | 同进程调用 |
| core → data | 文件读取 | JSON 文件 |
| nlu → data | 文件读取 | JSON + zh_mapping |
| scraper → paldb.cc | HTTP | HTML 抓取 |
| scraper → data/raw | 文件写入 | 中间格式 |

---

## 各包职责边界

### `packages/core` — 核心引擎

- **职责**: 纯算法，无 I/O 依赖（除 data_loader 读 JSON）
- **输入**: `schema.Pal` 实体、查询参数
- **输出**: BreedingTree、候选 Pal 列表
- **不依赖**: adapters、api、nlu、web
- **内含**: `schema.py` — 全项目唯一 canonical 数据规范

### `packages/adapters` — 外部数据适配

- **职责**: 对接外部数据源，统一转换为 `schema.Pal`
- **子包**:
  - `paldb/`: paldb.cc 爬虫 (scraper → parser → adapter)
  - `gamefile/`: FModel 游戏文件解包适配
- **输出**: `list[schema.Pal]`
- **依赖**: `packages/core` (仅 import schema)

### `packages/nlu` — 自然语言理解

- **职责**: 中文文本 → 结构化意图 + 实体
- **输入**: 用户原始文本
- **输出**: `Intent` + `ExtractedEntity`
- **依赖**: data/processed/zh_mapping.json

### `packages/api` — API 网关

- **职责**: HTTP 路由、参数校验、响应格式化
- **依赖**: core + nlu
- **框架**: FastAPI

### `packages/web` — 前端 UI

- **职责**: 搜索交互、配种树可视化、语音输入
- **依赖**: api (HTTP)
- **框架**: React 18 + Vite

### `packages/shared` — 跨包共享

- **职责**: TypeScript 类型定义 (`Pal`, `BreedingTree` 等接口)
- **被依赖**: web (类型引用)

---

## 数据流

```
用户输入 "手工10级的帕鲁"
  │
  ▼
web: SearchBox 组件捕捉 → POST /api/query/suitability
  │
  ▼
api: query.py → 调用 nlu.intent_classifier
  │
  ├── nlu: 分类 → IntentType.SUITABILITY_QUERY
  ├── nlu: 提取 → {work_type:"handiwork", level:10}
  │
  ▼
api: 调用 core.suitability_query.query("handiwork", 10)
  │
  ▼
core: 查询 pal_data → 返回候选列表 → 发现最高手工=6, 降级处理
  │
  ▼
api: 返回候选列表 → web 展示 CandidateList
  │
  ▼
用户选择 "阿努比斯" → POST /api/breeding/tree/Anubis
  │
  ▼
core: breeding_tree.build(Anubis) → BFS 反向搜索 → 递归展开
  │
  ▼
api: 返回 BreedingTree → web: BreedingTree 组件可视化渲染
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
