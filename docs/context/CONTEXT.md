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
│   ├── context/          ← AI 接手上下文
│   └── decisions/        ← 设计决策记录
│
├── packages/
│   ├── core/             ← 🧠 配种算法引擎 (Python)
│   │   ├── demo/         ←    快速验证脚本
│   │   └── pl_agent/core/
│   │       ├── schema.py      ← ★ canonical models
│   │       ├── errors.py      ← domain exceptions
│   │       ├── interfaces.py  ← ABCs
│   │       └── __tests__/     ← 单元测试
│   ├── adapters/         ← 🔌 外部数据适配
│   ├── api/              ← 🌐 FastAPI 服务
│   ├── nlu/              ← 💬 意图解析
│   └── web/              ← 🖥️ 前端 UI
│
├── data/                 ← 📊 数据文件
├── tests/                ← 🧪 集成/冒烟测试
├── init.md
└── README.md
```

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
| Schema 定义 | ✅ | `packages/core/pl_agent/core/schema.py` |
| 错误处理 | ✅ | `packages/core/pl_agent/core/errors.py` |
| 组件接口 | ✅ | `packages/core/pl_agent/core/interfaces.py` |
| pip 管理 | ✅ | uv workspace (`pyproject.toml`) |
| **数据层** | ✅ | **完成！** scraper + parser + adapter + validator |
| 单元测试 | ✅ | 5 个 parser 测试通过 |
| 数据加载器 | ✅ | `packages/core/pl_agent/core/data_loader.py` |
| 配种引擎 | ⬜ | `packages/core/pl_agent/core/breeding_engine.py` |
| 配种树构建 | ⬜ | `packages/core/pl_agent/core/breeding_tree.py` |
| 属性查询 | ⬜ | `packages/core/pl_agent/core/suitability_query.py` |
| NLU 模块 | ⬜ | `packages/nlu/` |
| API 服务 | ⬜ | `packages/api/` |
| 前端 UI | ⬜ | `packages/web/` |

---

## 下一步该做什么

按优先级:

1. **完成 paldb.cc 爬虫** — `packages/adapters/paldb/scraper.py` + `parser.py`，获取首批帕鲁数据
2. **跑通数据管线** — paldb.cc → adapter → `schema.Pal` → `data/processed/pal_data.json`
3. **实现配种引擎** — `packages/core/pl_agent/core/breeding_engine.py` (正向/反向计算)
4. **实现配种树构建** — `packages/core/pl_agent/core/breeding_tree.py` (BFS 递归展开)
5. **实现属性查询** — `packages/core/pl_agent/core/suitability_query.py`
6. **实现 NLU 模块** — `packages/nlu/`
7. **搭建 API 服务** — `packages/api/`
8. **前端 UI** — `packages/web/`

---

## 技术栈

- **后端**: Python 3.10+ / FastAPI
- **前端**: TypeScript / React 18 / Vite
- **数据**: JSON 文件 (数据量 < 500 条)
- **语音**: Web Speech API (MVP) → Whisper (进阶)
- **NLU**: 规则引擎 (MVP) → LLM (进阶)

---

## 关键算法参考

- **配种公式**: `child_rank = round((a.combi_rank + b.combi_rank) / 2)`，取最接近 CombiRank 的帕鲁
- **特殊规则**: 传说帕鲁同类繁殖、部分亚种固定父母组合、Boss 帕鲁不可配种
- **配种树**: BFS 反向搜索，visited 防循环，max_depth=5，按步数择优

参考项目: [azmiao/PalWorldPlugin](https://github.com/azmiao/PalWorldPlugin) (Python 配种算法，但数据已过期)

---

## 文件快速索引

| 想看什么 | 去哪个文件 |
|---------|-----------|
| 为什么这样设计 | `docs/architecture/ARCHITECTURE.md` |
| 目录怎么组织的 | `docs/architecture/PROJECT_STRUCTURE.md` |
| 🔑 数据模型规范 (Schema) | `packages/core/pl_agent/core/schema.py` |
| 🔑 数据层详细需求 | `docs/architecture/DATA_LAYER_REQUIREMENTS.md` |
| 🔌 外部数据如何接入 | `packages/adapters/base.py` + `docs/architecture/DATA_LAYER_REQUIREMENTS.md` §11 |
| ❗ 业务异常定义 | `packages/core/pl_agent/core/errors.py` |
| 🔧 引擎组件接口 | `packages/core/pl_agent/core/interfaces.py` |
| 配种算法怎么算 | `docs/architecture/ARCHITECTURE.md` §4 |
| API 有哪些接口 | `docs/architecture/ARCHITECTURE.md` §5 |
| AI 行为指引 | `.github/copilot-instructions.md` |
| 初始需求 | `init.md` |
