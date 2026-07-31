# Copilot 行为指引 — pl-agent

## 项目背景

这是一个**幻兽帕鲁配种 Agent** 项目，帮助玩家找到最优配种路径。
每次新会话开始时，请先阅读 `docs/context/CONTEXT.md`。

## 架构规则

- **唯一 Schema**: 所有数据模型必须使用 `packages/core/pl_agent/core/schema.py` 中的规范定义。禁止在项目中定义重复的数据类型。
- **数据库**: 5 表规范化设计 (`docs/architecture/DATABASE_DESIGN.md`)，SERIAL PK + game_id UK
- **适配器层**: 外部数据必须通过 `packages/adapters/` 中的适配器流入
- **禁止循环引用**: `core` → 无依赖，`adapters` → 仅依赖 `core`，`api` → 依赖 `core`

## 代码组织

- **单元测试**: 放在源码同目录的 `__tests__/` 下。命名规范: `test_*.py`。
- **集成测试**: 放在 `tests/integration/` 下，跨包联调测试。
- **冒烟测试**: 放在 `tests/smoke/` 下，核心流程端到端验证。
- **Demo 脚本**: 放在各包的 `demo/` 目录下，用于快速手动验证。
- **文档**: 按类型放在 `docs/architecture/`、`docs/context/`、`docs/decisions/` 下。

## 错误处理

- 使用 `pl_agent.core.errors` 中定义的异常类处理所有业务异常。
- 业务代码禁止抛出泛型 `Exception` 或 `ValueError`。
- 映射关系:
  - 适配器错误 → `AdapterError`
  - 数据校验错误 → `DataIntegrityError`
  - 配种问题 → `BreedingLoopError` / `PalNotFoundError`

## 数据来源

- 主数据源: [paldb.cc](https://paldb.cc/cn/) — 服务端渲染 HTML，可爬取解析。
- 配种公式: `子代 = 最接近 round((父A.CombiRank + 父B.CombiRank) / 2) 的帕鲁`
- 工作适应性: 12 种类型，等级范围 0-10（不设硬上限）。

## 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 模块 | `snake_case` | `routes/query.py` |
| Python 类 | `PascalCase` | `PostgresLoader` |
| Python 函数 | `snake_case` | `load_all()` |
| JSON 字段 | `snake_case` | `combi_rank` |
| 测试文件 | `test_*.py` | `test_api_smoke.py` |
| 测试函数 | `test_功能描述` | `test_smart_query_name` |

## 修改代码前

1. 先读 `docs/context/CONTEXT.md` 了解项目全貌
2. 查看 `docs/architecture/DATABASE_DESIGN.md` 了解 5 表规范化设计
3. 确认改动符合 `docs/architecture/PROJECT_STRUCTURE.md` 中的目录规范
4. 新增数据字段 → 先改 `schema.py`，再改 adapter/loader，最后改 routes/query.py
5. 修改数据库 → 更新 `data/sql/002_normalize.sql` + `DATABASE_DESIGN.md`

## 数据流

```
paldb.cc → adapters/paldb/scraper.py → parser.py → adapter.py → schema.Pal
                                                                      │
                                          ┌───────────────────────────┘
                                          ▼
                              adapters/postgres/adapter.py
                              (4 表事务: pal + element + aliase + work)
                                          │
                                          ▼
                                    PostgreSQL 16
                              (5 表: pal/pal_element/
                               work_suitability/pal_aliase/
                               breeding_rule)
                                          │
                              adapters/postgres/loader.py
                              (LOAD_ALL_SQL: 4 表 JOIN 拼装)
                                          │
                                          ▼
                              api/routes/query.py (SQL 直连)
```

任何新增数据源都走同样的 adapter 模式，不允许裸调外部 API 进入 core。

1. Read `docs/context/CONTEXT.md`
2. Check `docs/architecture/` for relevant design docs
3. Ensure changes align with the monorepo structure in `docs/architecture/PROJECT_STRUCTURE.md`
