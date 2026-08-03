# Text-to-SQL 实施执行计划

> 版本: v1.0 | 日期: 2026-08-02 | 状态: OK 已完成（P0-P2 全部落地，见 TEXT2SQL_PLAN.md 实施记录）
> 依据: [TEXT2SQL_PLAN.md](./TEXT2SQL_PLAN.md)（方案）、[Text-to-SQL.md](../../context/Text-to-SQL.md)（原始需求）
> 分支: feature/tcimba-22tables

---

## 0. 执行前已核实的项目事实

| 项 | 实际状态 | 影响 |
|----|---------|------|
| API 路由 | `routes/query.py` 用 `APIRouter(prefix="/api")`，`main.py` include | 新端点建独立 `routes/sql_query.py` |
| 请求模型 | `api/__init__.py` 有 `QueryRequest`；需新增 `SqlQueryRequest` | 放同文件或独立 models |
| 错误格式 | `formatter.format_error(code, message)` → `{success:false, error:{code,message}}` | SQL 端点复用 |
| DB session | `db/session.py` 的 `create_engine_and_sessionmaker()` + `OrmQueryService` | SQL 执行复用 engine |
| seed DDL | `seed_tcimba_full.py` 的 `_apply_ddl()` 拆分 `;` 执行 | 视图 DDL 复用该机制 |
| Tool 抽象 | `tools/base.py` 的 `Tool`（name/description/parameters/run） | 新工具继承 |
| 工具注册 | `tools/breeding.py` 的 `build_breeding_tools()` 返回 list | 追加 RunSqlQueryTool |
| 客户端 | `BreedingApiClient._request(method, path, **kwargs)` 支持 `json=` | 加 run_sql_query 方法 |
| API 单测 | `__tests__/test_api_smoke.py` 用 urllib 打 http://localhost:8000 | 冒烟测试追加 |
| API 单测 | `__tests__/test_orm_queries.py` 用 pytest + async | SQL 单测参考此模式 |
| 依赖 | `packages/api/pyproject.toml` 无 sqlglot | 需 `uv add sqlglot` |
| pal_stats NULL | `v_pal_full` LEFT JOIN pal_stats，无 stats 帕鲁为 NULL | 提示词注明 |

---

## P0 — API 安全执行器（后端兜底层）

> 目标：`POST /api/sql/query` 可安全执行白名单视图的 SELECT，返回 columns/rows。

### P0.1 新增依赖 `sqlglot`
- 在 `packages/api/pyproject.toml` 的 dependencies 加 `"sqlglot>=25.0"`
- 本机执行 `uv add sqlglot --directory packages/api`（或手工加依赖后 `uv sync`）

### P0.2 新增视图 DDL `data/sql/004_text2sql.sql`
- 内容：`CREATE OR REPLACE VIEW v_pal_full / v_item_drop / v_skill_learn`（按方案 3.3 的 SQL）
- 幂等方式：`CREATE OR REPLACE VIEW`（PG 不支持 CREATE VIEW IF NOT EXISTS）
- **应用方式**：在 `seed_tcimba_full.py` 中追加对 `DDL_004` 的 `_apply_ddl()` 调用；
  本地测试时可直接 `psql -f` 或 docker exec 执行

### P0.3 新增请求模型
- `packages/api/pl_agent/api/__init__.py` 加：
  ```python
  class SqlQueryRequest(BaseModel):
      sql: str
  ```

### P0.4 新增安全执行器 `routes/sql_query.py`
- 位置：`packages/api/pl_agent/api/routes/sql_query.py`
- `router = APIRouter(prefix="/api")`
- 端点 `POST /sql/query`：
  1. `body = SqlQueryRequest.model_validate(await request.json())`
  2. **防火墙①只读校验**：`sqlglot.parse(sql, read="postgres")`
     - `len(parsed) != 1` → `SQL_BLOCKED`
     - 语句类型非 `Select` / With 内层非 Select → `SQL_BLOCKED`
     - `parse` 抛异常 → `SQL_SYNTAX`
  3. **防火墙②白名单表**：AST `find_all(exp.Table)` 提取表名（去引号），
     全部必须在 `{v_pal_full, v_item_drop, v_skill_learn}` → 否则 `SQL_BLOCKED`
  4. **防火墙③强制 LIMIT**：AST 检查是否有 limit；
     - 无 → `expression.limit(100)`
     - 有 → min(用户值, 200)
     - 检查 offset：`offset + limit ≤ 500` → 否则 `SQL_BLOCKED`
     - `transpile(read="postgres")[0]` 生成最终 SQL
  5. **防火墙④超时熔断**：`asyncio.wait_for(execute, timeout=3)`
  6. **执行（复用单例 engine，不新建连接）**：
     - 在 `db/queries.py` 的 `OrmQueryService` 新增**公开方法** `execute_raw_sql(sql) -> {columns, rows}`：
       ```python
       async def execute_raw_sql(self, sql: str) -> dict:
           async with self._session_factory() as session:
               result = await session.execute(text(sql))
               columns = list(result.keys())
               rows = [list(r) for r in result.all()]
               return {"columns": columns, "rows": rows, "row_count": len(rows)}
       ```
     - 端点内 `orm_service: OrmQueryService = request.app.state.orm_service`，调 `execute_raw_sql(final_sql)`
     - 这样复用 app.state 的单例 engine（与既有端点一致），避免 sql_query.py 自行建连接
  7. 返回 `format_success({...})`
  - 异常映射：超时 → `SQL_TIMEOUT`；其他 → `SQL_ERROR`
- `main.py` 注册：`from .routes.sql_query import router as sql_router` + `app.include_router(sql_router)`

### P0.5 单元测试 `__tests__/test_sql_query.py`
- **两类拆分**（防火墙逻辑可纯单测，真实执行依赖 DB）：
  1. **纯单测（mock，不碰 DB）**：将安全校验抽成可独立测试的函数
     （如 `validate_sql(sql) -> (ok, error_code, final_sql)` 或独立 `SqlGuard` 类），
     用 pytest 直接测：
     - 允许：`SELECT * FROM v_pal_full LIMIT 5` → ok
     - 拦截：DELETE / DROP / UPDATE / 多语句(`;`) / 非白名单表 / OFFSET 超限
     - LIMIT：自动追加 100 / 钳制 200
     - 非法 SQL → SQL_SYNTAX（返回 code 而非抛 500）
     - LIMIT 改写后 `transpile` 语法有效
  2. **冒烟测试（真实 DB，放 `test_api_smoke.py`）**：`POST /api/sql/query` 真实执行
     - `SELECT cn_name FROM v_pal_full LIMIT 3` → success 且 row_count ≤ 3
     - `DROP TABLE x` → not success, code=SQL_BLOCKED
- 说明：SQL 端点**不走** `test_orm_queries.py` 的 mock-session 模式（那个是测 ORM 方法）；
  SQL 端点测防火墙用纯函数，测执行用真实 DB 冒烟。

### P0.6 冒烟测试追加
- `__tests__/test_api_smoke.py` 追加（与 P0.5 的真实 DB 冒烟合并）：
  - `post("/api/sql/query", {"sql": "SELECT cn_name FROM v_pal_full LIMIT 3"})` → success
  - `post("/api/sql/query", {"sql": "DROP TABLE x"})` → not success, code=SQL_BLOCKED

---

## P1 — Agent 工具接入

> 目标：LLM 可通过 `run_sql_query` 工具在长尾问题时取数。

### P1.1 新增客户端方法
- `packages/agent/pl_agent/agent/clients/breeding_api_client.py` 加：
  ```python
  async def run_sql_query(self, sql: str) -> dict:
      return await self._request("POST", "/api/sql/query", json={"sql": sql})
  ```
- 复用 `_request`（已支持 json= 和 UpstreamEnvelope 校验）

### P1.2 新增工具 `tools/sql_query.py`
- 按方案 5.1 的 `RunSqlQueryTool`：
  - name=`run_sql_query`
  - description：长尾问题兜底 + 三张白名单视图 + 只写 SELECT + LIMIT + 示例 SQL
  - parameters：`sql` 字符串
  - `run()`：调 `client.run_sql_query(sql)`，返回结果 dict

### P1.3 注册到 `build_breeding_tools()`
- `tools/breeding.py` 的 `build_breeding_tools()` 追加 `RunSqlQueryTool(client)`

### P1.4 提示词注入
- `prompts/assistant.md` 增加：
  1. **工具总览**段补 `run_sql_query`（长尾兜底）
  2. **【数据库宽表】**段（按方案 5.4）：三视图字段 + 用法 + NULL 语义 + 纠错引导
  3. **【工具优先级】**段（按方案 5.5）：常规工具 > run_sql_query > 玩法知识直答

### P1.5 Agent 工具测试 `tools/__tests__/test_sql_query_tool.py`
- 参考 `test_pal_info_tools.py`
- `test_tool_registered`：build_breeding_tools 含 run_sql_query
- `test_tool_calls_client`：run() 调 client.run_sql_query（mock client）
- `test_description_mentions_readonly`：description 含"只读/SELECT/LIMIT"

---

## P2 — 回归与端到端验证

- `make test-all`（或分包测试：api + agent + agent-web）
- Docker 重建 api + agent-web 镜像
- 浏览器端到端：
  - 常规问题仍走旧工具（如"金属锭怎么做" → query_item_recipe）
  - 长尾问题走 SQL（如"体型是 L 且跑得快的帕鲁" → run_sql_query）
- 确认无回归（配种/工种/技能/被动/物品/详情 6 大场景）

---

## 3. 执行顺序与依赖

```
P0.1(sqlglot) → P0.2(视图DDL) → P0.3(模型) → P0.4(端点) → P0.5/0.6(测试)
                                                    ↓
P1.1(client) → P1.2(工具) → P1.3(注册) → P1.4(提示词) → P1.5(测试)
                                                    ↓
P2(回归 + Docker + 浏览器验证)
```

---

## 4. 风险与回滚

| 风险 | 应对 |
|------|------|
| sqlglot 解析 LLM 复杂 SQL 失败 | 返回 SQL_SYNTAX，LLM 收到后改写重试（提示词已引导） |
| 视图查询性能 | 数据 <2MB，普通视图聚合开销可忽略；必要时加索引 |
| SQL 工具被滥用 | 提示词工具优先级 + 白名单视图限制 |
| `execute_raw_sql` 引入 raw SQL 执行面 | 仅限白名单视图 + 四道防火墙 + 复用单例 engine（与既有端点同源） |
| 全量回归失败 | P2 单独做，发现问题回滚对应 commit |

---

## 5. 完成定义（DoD）

- [ ] `POST /api/sql/query` 通过四道防火墙测试
- [ ] `v_pal_full / v_item_drop / v_skill_learn` 视图可用
- [ ] `run_sql_query` 工具注册并可被 LLM 调用
- [ ] 提示词包含宽表 DDL + 工具优先级
- [ ] 全部单测通过 + 浏览器端到端验证长尾问题走 SQL、常规问题不回归
- [ ] 提交代码（沙箱连不上 GitHub，需用户终端 push）
