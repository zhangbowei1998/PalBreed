# API 数据访问 ORM 迁移计划

> 版本: v2.1 | 日期: 2026-08-01 | 状态: 已完成

---

## 1. 目标与范围

### 1.1 迁移目标

将 `packages/api` 的数据库访问方式由 `asyncpg + 原生 SQL` 迁移为 `SQLAlchemy Async ORM`，并保持以下不变：

- 对外 API 路径与响应结构
- 业务规则（配种公式、特殊规则优先级、超范围回退）
- PostgreSQL 不可用时 JSON 降级策略

### 1.2 本次范围

在本次改造中，`API` 运行时和启动加载涉及的数据库操作统一迁移到 ORM：

- 启动加载全量帕鲁
- 名称查询配种父母对
- 特殊配种规则守卫
- 工种等级筛选
- 工种统计查询

### 1.3 非范围

- `packages/adapters` 的写入链路（爬虫入库）
- 数据库 DDL 结构（`data/sql/002_normalize.sql`）
- 前端接口契约

---

## 2. 现状问题

1. API 层存在数据库连接与 SQL 细节泄漏到路由逻辑（可维护性低）。
2. 查询分散在多个模块，复用能力弱。
3. 原生 SQL 字符串较多，不利于类型感知和结构化重构。
4. 生命周期管理依赖底层连接池细节，扩展困难。

---

## 3. 目标架构

```
FastAPI Route
   │
   ▼
OrmQueryService (业务查询服务)
   │
   ▼
SQLAlchemy AsyncSession
   │
   ▼
ORM Models (pal/work_suitability/...)
   │
   ▼
PostgreSQL
```

关键点：

- 路由不直接触达连接池。
- ORM 模型集中在 `api/db/models.py`。
- 查询逻辑集中在 `api/db/queries.py`。
- `lifespan` 初始化 `OrmQueryService`，并保留 JSON 降级。

---

## 4. 详细执行计划

### Phase A: 依赖与基础设施

- 修改 `packages/api/pyproject.toml`：新增
  - `sqlalchemy>=2.0`
  - `asyncpg>=0.30`
- 新增 `packages/api/pl_agent/api/db/`
  - `base.py`：Declarative Base
  - `models.py`：ORM 表映射
  - `session.py`：异步 engine / sessionmaker
  - `queries.py`：统一查询服务

验收：

- API 包可成功导入 ORM 模块，无循环依赖。

### Phase B: 启动加载迁移

- 改造 `packages/api/pl_agent/api/main.py`
  - 使用 `OrmQueryService.load_all_pals()` 构建 `QueryParser`
  - 将 `orm_service` 挂载到 `app.state`
  - 保留异常回退到 JSON 加载

验收：

- `/health` 正常返回，且 `pals_loaded > 0`（PG 可用场景）。

### Phase C: 路由查询迁移

- 改造 `packages/api/pl_agent/api/routes/query.py`
  - 删除路由内直接操作连接池的代码
  - 使用 `OrmQueryService` 执行：
    - `get_breeding_rules_by_game_id`
    - `get_pal_pair_by_db_id`
    - `query_parent_pairs_by_rank`
    - `query_suitability`
    - `get_work_stats`

验收：

- `/api/query` 名称查询与属性查询均可用。
- `/api/suitability/stats` 返回结构不变。

### Phase D: 文档同步

- 更新需求文档中“技术选型”和“数据访问方式”描述。
- 更新架构文档中 API 数据访问层图示与说明。
- 更新上下文文档，补充 AI 接手指引。

验收：

- 文档可清晰回答“数据库访问在哪里、怎么改、如何扩展”。

### Phase E: 验证与收尾

- 运行关键接口 smoke 验证。
- 若出现类型或行为偏差，优先保持向后兼容。

验收：

- 核心路径全部通过：
  - `POST /api/query`（名称）
  - `POST /api/query`（工种）
  - `GET /api/suitability/stats`
  - `GET /health`

---

## 5. 回滚策略

若 ORM 改造导致严重回归：

1. 回退 `main.py` 和 `routes/query.py` 到上一版。
2. 保留 `db/` 目录但不启用。
3. 通过分支恢复 `asyncpg + SQL` 路径。

---

## 6. 风险与对策

1. 配种 CROSS JOIN 逻辑在 ORM 表达中的可读性下降。
- 对策：使用 `aliased(PalModel)` + 明确注释，必要时保留 SQLAlchemy `text` 作为兜底。

2. API 响应字段可能在改造中被意外改变。
- 对策：以现有 formatter 为唯一输出层，路由只替换数据来源。

3. 启动阶段若 ORM 初始化失败可能导致服务不可用。
- 对策：保留 JSON fallback，确保最小可用。

---

## 7. 执行记录

- [x] 读取并确认现有架构与数据库文档
- [x] 产出完整 ORM 迁移计划
- [x] 引入 ORM 依赖与模块
- [x] API 路由迁移完成
- [x] 文档更新完成
- [x] 关键接口验证完成

验证摘要（2026-08-01）：

- API 冒烟脚本通过 8/8（health、name_query、suitability、out_of_range、pal_detail、breeding_tree、stats、not_found）。
- `pl_agent.api.main` 在项目 PYTHONPATH 下可正常导入。
- 新增 `OrmQueryService` 单元测试 7/7 通过（不依赖真实 PostgreSQL，使用 AsyncSession mock）。
