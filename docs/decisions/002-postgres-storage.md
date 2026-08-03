# ADR 002: JSON → PostgreSQL 数据存储迁移

> 日期: 2026-07-31 | 状态: OK 已落地（方案 B 演进为 SQLAlchemy Async ORM 配种查询，见 MIGRATION_PLAN.md） | 决策者: AI + 用户

---

## 背景

当前项目使用 JSON 文件 (`data/processed/pal_data.json`) 作为帕鲁数据的唯一持久化存储。数据量 < 500 条，JSON 文件方案在原型阶段运行良好。

但随着项目发展，用户希望引入 PostgreSQL 来替代 JSON 文件存储。

## 问题陈述

JSON 文件方案在以下场景存在局限：

1. **查询能力弱** — 只能在 Python 内存中遍历查询，无法用 SQL
2. **无并发控制** — 多进程同时写入无保护
3. **数据分析困难** — 每次分析都需要写 Python 脚本
4. **无法增量更新** — 新增一条帕鲁也需要全量重写文件

## 方案对比

### 方案 A: PostgreSQL 作为唯一存储

- 所有读写都走 PG
- API 每次请求都查询数据库
- ❌ 配种引擎 BFS 搜索需要频繁查 CombiRank，网络开销太大

### 方案 B: PostgreSQL 持久化 + 热缓存/冷查询分层 (选中)

- **热缓存 (启动时)**: 从 PG 提取配种必需的 4 个字段 (`id`, `combi_rank`, `is_wild`, `work_suitability`) 到内存 `BreedingIndex` (~10KB)
- **冷查询 (运行时)**: 展示字段 (`image_url`, `wiki_url` 等)、统计聚合、管理查询走 PG 直连
- PG 不可用时降级到 JSON 文件
- ✅ 配种性能保证 (内存 O(1)) + PG 真正发挥 SQL 查询/分析价值

### 方案 C: SQLite

- 单文件，零配置
- ❌ 缺乏 PG 的并发能力、JSONB 索引、生态工具

## 决策

**选择方案 B — PostgreSQL 持久化 + 内存热加载**

核心原则：

1. **引擎不碰数据库** — `core` 包不引入任何数据库依赖，只操作内存中的轻量 `PalRef`
2. **热缓存 + 冷查询分层** — 配种核心字段（~10KB）内存常驻；展示字段 PG 按需查询
3. **JSON 兼容降级** — PG 不可用时自动回退到 JSON 文件的全量加载
4. **Adapter 模式** — 新代码放入 `adapters/postgres/`，与 `adapters/paldb/` 同级

## 架构影响

```
paldb.cc → scraper → parser → PalDBAdapter
                                  │
                                  ├─→ pal_data.json   (保留兼容)
                                  └─→ PostgresWriter  (新增)
                                       │
                                       └─→ PostgreSQL
                                            pals 表
                                            breeding_rules 表

启动时 (热缓存):
  PostgresLoader.load_hot()
    SELECT id, combi_rank, is_wild, handiwork, ..., farming FROM pals
    → BreedingIndex (内存 ~10KB)
  └─ 失败 → DataLoader.load(pal_data.json)  (降级: 全量 JSON)

运行时 (冷查询):
  API 详情 → PG: SELECT * FROM pals WHERE id = $1
  统计面板 → PG: SELECT MAX(handiwork), AVG(...) FROM pals
  候选筛选 → PG: SELECT id, cn_name FROM pals WHERE handiwork >= 4
```

## Schema 设计

工作适应性用 12 个独立 INTEGER 列而非 JSONB，理由：
- SQL 原生查询: `WHERE handiwork >= 4` 比 `WHERE (ws->>'handiwork')::int >= 4` 简洁
- 可建 B-tree 索引，查询更快
- 工种类型固定 12 种，不频繁变化

## 依赖变更

```diff
# packages/adapters/pyproject.toml
+ "asyncpg>=0.30"
```

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| PG 连接失败导致服务无法启动 | JSON 降级：自动回退到 `DataLoader` |
| PG Schema 变更遗漏 | SQL 迁移脚本纳入版本控制 (`data/sql/`) |
| asyncpg 学习成本 | adapter 代码量 < 100 行，接口简单 |

## 相关文档

- `docs/architecture/archive/DATA_LAYER_REQUIREMENTS.md` §12 — 详细 Schema 及实现步骤（已归档，paldb 时代）
- `docs/architecture/design/DATABASE_DESIGN_TCIMBA_V2.md` — 22 表最终设计（现状）
- `docs/architecture/plans/MIGRATION_PLAN.md` — ORM 迁移执行记录
- `docs/context/CONTEXT.md` — 项目结构与数据流
- `packages/adapters/` — 现有 JSON adapter 参考
