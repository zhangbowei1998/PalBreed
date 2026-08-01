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
| 🤖 **Agent 对话** | `packages/agent`（纯逻辑）+ `packages/agent-web`（FastAPI 服务）— LLM function calling 聊天、配种工具调用 |
| 🧠 **记忆系统** | 短期记忆（会话内）+ 长期记忆（跨会话按用户，PG 持久化）+ LLM 上下文压缩 |
| 👤 **用户体系** | 注册/登录/token，长期记忆按用户隔离（前端登录页后续补充） |

## 快速开始

### 方式一：Docker 部署（推荐，一键启动全部）

```bash
# 1. 准备环境变量（DeepSeek API key 必填）
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY 和 AUTH_SECRET

# 2. 启动全部服务（postgres + api + agent-web + web）
docker compose up -d --build

# 3. 访问
#    前端:     http://localhost:8080
#    配种 API: http://localhost:8000
#    Agent:    http://localhost:9000
```

Docker 部署会：
- 自动建表（5 表规范化）+ 从 `data/processed/pal_data.json` 灌入 288 只帕鲁
- agent-web 自动连 PG 做长期记忆持久化 + 用户体系
- nginx 统一入口：`/agent/*` `/auth/*` → agent-web，`/api/*` → api（同源无跨域）

> 云部署：同一份 compose 配置可直接用于云主机（改端口、加反向代理/HTTPS 即可）。

### 方式二：本地开发模式

```bash
# 克隆项目
git clone <repo-url>
cd pl-agent

# 启动 PostgreSQL（必需）
docker compose up -d postgres

# 后端（配种 API）
uv sync
make serve

# Agent 服务
make serve-agent-service

# 前端 (另一个终端)
make serve-web
```

### 统一命令入口（Makefile）

```bash
# 启动现有 API
make serve

# 启动 agent-web（聊天 Agent 服务）
make serve-agent-service

# 启动 web 前端
make serve-web

# 仅跑 agent 模块测试
make test-agent

# 跑 agent-web 服务测试
make test-agent-web

# 根项目全量测试（含 agent / agent-web）
make test-all

# 仅做 web 构建校验
make test-web
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
│   ├── api/              ← 🌐 FastAPI 服务（配种查询）
│   ├── agent/            ← 🤖 独立 agent 模块（LLM/tools/记忆/用户，无 web 依赖）
│   ├── agent-web/        ← 🌐 agent 的 FastAPI 服务层（服务前端）
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
| 数据源 | PostgreSQL 16（由 paldb.cc 抓取后入库） |
| 语音 | Web Speech API (MVP) → Whisper (进阶) |
| NLU | 规则引擎 (MVP) → LLM (进阶) |

## 数据来源

基础数据来自 [paldb.cc](https://paldb.cc/cn/)，通过离线爬虫脚本抓取后写入 PostgreSQL；API 运行时仅从数据库读取，不再使用 JSON 降级。

关键数据字段：
- **CombiRank** — 官方繁殖力值，配种计算核心
- **工作适应性** — 12 种工作类型及等级
- **属性、稀有度** — 辅助筛选

## 开发状态

🚧 持续迭代中，详见 [`docs/context/CONTEXT.md`](./docs/context/CONTEXT.md)

## 许可

MIT
