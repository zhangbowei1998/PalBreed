# 幻兽帕鲁配种 Agent

> 🥚 输入想要的帕鲁，输出从基础帕鲁开始的完整配种方案

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.1-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![License](https://img.shields.io/badge/license-MIT-blue)](./LICENSE)

---

## 这是什么

一个智能化的幻兽帕鲁配种助手。用自然语言描述你想要的帕鲁（打字或语音），系统会先筛选候选，再基于 CombiRank 计算配种父母组合。

**示例**：

```
输入:  "我要一个手工10级的帕鲁"
输出:  手工最高为 Lv6，符合条件的帕鲁:
       1. 阿努比斯 (手工6, 采矿6, 搬运4)
       2. ...
       请选择 →
       
输入:  "1" (或"阿努比斯")
输出:  🌿 野外捕获: 棉悠悠 + 捣蛋猫
       🥚 配种:     棉悠悠 + 捣蛋猫 = 疾旋鼬
       🥚 配种:     疾旋鼬 + 烽歌龙 = 🎯 阿努比斯
```

## 功能

| 功能 | 说明 |
|------|------|
| 🔍 **名称直查** | 输入帕鲁名 → 返回父母组合（一级） |
| 🏭 **属性反向查** | 输入"手工10级" → 列出所有符合的帕鲁 → 选一个 → 父母组合 |
| 🎤 **语音输入** | 支持语音描述需求 (Web Speech API) |
| 🧮 **ORM 配种查询** | API 通过 SQLAlchemy Async ORM 访问 PostgreSQL，执行 CROSS JOIN 公式查询 |
| 📊 **工种统计** | 输出 12 工种 max/avg/count 统计 |

## 快速开始

```bash
# 克隆项目
git clone <repo-url>
cd pl-agent

# 后端
cd packages/api
pip install -r requirements.txt
uvicorn pl_agent.api.main:app --reload

# 前端 (另一个终端)
cd packages/web
npm install
npm run dev
```

### 统一命令入口（Makefile）

```bash
# 启动现有 API
make serve

# 启动 agent-service
make serve-agent-service

# 仅跑 agent-service 测试
make test-agent-service

# 跑 agent-service 契约测试
make test-contract-agent-service

# 根项目全量测试（含 agent-service）
make test-all
```

## 项目结构

```
pl-agent/
├── .github/              ← 🤖 AI 行为指引
├── docs/                 ← 📖 项目文档（⭐ AI 接手先读这里）
│   ├── architecture/     ←    架构设计
│   ├── context/          ←    快速上下文
│   └── decisions/        ←    设计决策
├── packages/             ← 📦 Monorepo 业务包
│   ├── core/             ← 🧠 配种算法引擎 + Schema
│   ├── adapters/         ← 🔌 外部数据适配层
│   ├── api/              ← 🌐 FastAPI 服务
│   ├── nlu/              ← 💬 意图解析
│   ├── web/              ← 🖥️ 前端 UI
│   └── shared/           ← 🔗 跨包类型
├── data/                 ← 📊 帕鲁数据 (来自 paldb.cc)
├── tests/                ← 🧪 集成/冒烟测试
├── init.md               ← 原始需求
└── README.md
```

## 文档

| 文档 | 内容 |
|------|------|
| [`docs/context/CONTEXT.md`](./docs/context/CONTEXT.md) | 🔰 AI 接手快速上下文 |
| [`docs/architecture/ARCHITECTURE.md`](./docs/architecture/ARCHITECTURE.md) | 🏗️ 完整架构设计 |
| [`docs/architecture/PROJECT_STRUCTURE.md`](./docs/architecture/PROJECT_STRUCTURE.md) | 📁 目录与依赖关系 |
| [`docs/architecture/MIGRATION_PLAN.md`](./docs/architecture/MIGRATION_PLAN.md) | 🛠️ ORM 迁移计划与执行记录 |

## 技术栈

| 层 | 技术 |
|----|------|
| 核心引擎 | Python 3.10+ |
| API 服务 | FastAPI |
| 数据访问 | SQLAlchemy Async ORM + asyncpg |
| 前端 | React 18 + Vite + TypeScript |
| 数据源 | [paldb.cc](https://paldb.cc/cn/) (游戏数据, 持续更新) |
| 语音 | Web Speech API (MVP) → Whisper (进阶) |
| NLU | 规则引擎 (MVP) → LLM (进阶) |

## 数据来源

数据来自 [paldb.cc](https://paldb.cc/cn/)，一个持续维护的幻兽帕鲁数据库网站（基于游戏解包数据）。通过离线爬虫脚本获取，存储为本地 JSON 文件。

关键数据字段：
- **CombiRank** — 官方繁殖力值，配种计算核心
- **工作适应性** — 12 种工作类型及等级
- **属性、稀有度** — 辅助筛选

## 开发状态

🚧 持续迭代中，详见 [`docs/context/CONTEXT.md`](./docs/context/CONTEXT.md)

## 许可

MIT
