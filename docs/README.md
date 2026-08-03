# 📖 项目文档总索引

> **版本 0.1.0** | 幻兽帕鲁配种 Agent 文档导航
> AI/新开发者接手：**先读 [context/CONTEXT.md](./context/CONTEXT.md)** 了解现状，
> 再按本页分类目录按需深入。

---

## 🧭 文档地图（分类导航）

| 分类 | 目录 | 作用 | 代表性文档 |
|------|------|------|-----------|
| **上下文** | [`context/`](./context/) | 🔰 **AI 接手入口**，项目现状快照 | `CONTEXT.md`（唯一 SSOT） |
| **现状设计** | [`architecture/design/`](./architecture/design/) | 🏗️ 当前生效的架构/DB/API 设计 | `DATABASE_DESIGN_TCIMBA_V2.md` |
| **Agent 实现** | [`architecture/agent/`](./architecture/agent/) | 🤖 agent/agent-web 包级实现说明 | `README.md` + 01~10 |
| **计划** | [`architecture/plans/`](./architecture/plans/) | 📋 已执行/进行中的开发计划 | `TCIMBA_DATA_DEVELOPMENT_PLAN.md` |
| **需求** | [`architecture/requirements/`](./architecture/requirements/) | 📐 需求基线（FR/NFR） | `AGENT_BREEDING_CHAT_REQUIREMENTS.md` |
| **部署运维** | [`architecture/deploy/`](./architecture/deploy/) | 🚀 阿里云部署 + CI/CD | `ALIYUN_DEPLOY.md` |
| **决策记录** | [`decisions/`](./decisions/) | 🧾 ADR 设计决策 | `003-feature-gaps.md` |
| **问题记录** | [`bug/`](./bug/) | 🐛 历史 Bug 复盘 | `20260802.md` |
| **归档** | [`architecture/archive/`](./architecture/archive/) | 📦 已废弃/被取代文档 | `CORE_ENGINE_REQUIREMENTS.md` |

---

## 📂 目录结构

```
docs/
├── README.md                          ← 本页（总索引）
├── context/
│   ├── CONTEXT.md                     ⭐ 唯一现状快照（SSOT，AI 接手先读）
│   ├── TCIMBA_DATA.md                 数据源文件清单
│   └── Text-to-SQL.md                 原始需求备忘
├── architecture/
│   ├── design/                        ← 现状设计（active）
│   │   ├── PROJECT_STRUCTURE.md
│   │   ├── DATABASE_DESIGN.md         ← v1.1 基础 5 表（历史基础版）
│   │   ├── DATABASE_DESIGN_TCIMBA_V2.md  ← v2.0 全量 22 表（现状核心）
│   │   └── API_REQUIREMENTS.md
│   ├── agent/                         ← Agent 实现专项（最贴近代码）
│   │   ├── README.md
│   │   └── 01_SERVICE_OVERVIEW.md ... 10_DELIVERY_PLAN.md
│   ├── plans/                         ← 开发计划（implemented）
│   │   ├── TCIMBA_DATA_DEVELOPMENT_PLAN.md
│   │   ├── TIER_IMPLEMENTATION_PLAN.md    ← 三层接入执行计划
│   │   ├── TIER_INTEGRATION_PLAN.md       ← 三层接入总览（已被上者取代）
│   │   ├── TEXT2SQL_PLAN.md               ← Text-to-SQL 方案
│   │   ├── TEXT2SQL_EXECUTION_PLAN.md     ← Text-to-SQL 执行计划
│   │   └── MIGRATION_PLAN.md
│   ├── requirements/                 ← 需求基线
│   │   ├── AGENT_BREEDING_CHAT_REQUIREMENTS.md
│   │   └── DATA_LAYER_REQUIREMENTS.md
│   ├── deploy/
│   │   └── ALIYUN_DEPLOY.md
│   └── archive/                      ← 已归档（archived）
│       ├── ARCHITECTURE.md               ← 旧版全景（paldb 时代）
│       ├── CORE_ENGINE_REQUIREMENTS.md   ← 引擎层已废弃
│       ├── AGENT_BREEDING_CHAT_ARCHITECTURE.md
│       └── AGENT_BREEDING_CHAT_PROJECT_STRUCTURE.md
├── decisions/                        ← ADR
│   ├── 002-postgres-storage.md
│   └── 003-feature-gaps.md
└── bug/
    └── 20260802.md
```

---

## 📌 文档生命周期状态约定

每个文档头部建议标注状态，AI 可据此判断是否应参考：

| 状态 | 含义 | 应否参考 |
|------|------|---------|
| `active` | 当前生效的设计/需求 | ✅ 必须参考 |
| `implemented` | 已实施完成的计划（历史执行记录） | 🔵 参考结论与坑点 |
| `archived` | 已废弃/被取代 | ⛔ 仅供历史溯源 |

---

## 🔗 快速上手路径

1. **了解项目**：`context/CONTEXT.md`
2. **看数据库**：`architecture/design/DATABASE_DESIGN_TCIMBA_V2.md`
3. **看 Agent 实现**：`architecture/agent/README.md`
4. **看 API**：`architecture/design/API_REQUIREMENTS.md`
5. **本地跑起来**：根 [`README.md`](../README.md) 快速开始

## 🏷️ 版本记录

- **v0.1.0**（2026-08-02）：文档分类重组——新增本索引，按 上下文/设计/实现/计划/需求/部署/决策/归档 分类，统一文档状态标注。
