# Text-to-SQL 兜底能力 — 修改方案

> 版本: v1.0 | 日期: 2026-08-02 | 状态: OK 已实施完成（P0-P3 落地，SqlGuard 16 单测 + run_sql_query 工具上线）
> 依据: [Text-to-SQL.md](../../context/Text-to-SQL.md) 的设计思路 + 当前项目架构

---

## 1. 背景与目标

### 1.1 现状问题

当前 Agent 的能力边界由**已实现的 9 个工具**决定：

| 工具 | 覆盖场景 |
|------|---------|
| `query_parent_pairs` | 帕鲁配种组合 |
| `resolve_pal` | 帕鲁基础信息 |
| `query_top_suitability` | 工种最高/最强 |
| `query_pal_stats` | 数据库统计 |
| `query_pals_by_passive` | 被动技能反查 |
| `query_pal_skills` | 帕鲁可学技能 |
| `query_pal_detail` | 帕鲁全量详情 |
| `query_item_drops` | 物品掉落来源 |
| `query_item_recipe` | 物品制作配方 |

当用户提问超出这 9 个工具能覆盖的场景时（**长尾问题**），Agent 只能：
- 依赖自身预训练知识回答（**脱离数据库**，可能编造数据）
- 或拒绝/兜底回复"未命中业务意图"

### 1.2 目标

引入 **Text-to-SQL + Tool/Function Calling** 作为兜底机制：
- 用户问长尾问题时，Agent 根据**数据库表结构（DDL）**生成 SELECT SQL
- 通过 `run_sql_query` 工具调用后端**安全执行器**取数
- 结构化数据返回给 LLM，LLM 结合查询结果回答

### 1.3 设计原则

1. **保留旧 API**：9 个既有工具仍为**第一优先**（精准、稳定、参数化、无注入面）
2. **Text-to-SQL 仅兜底**：匹配不到既有工具时才启用
3. **物理隔离执行**：Agent 生成的 SQL 只是字符串，执行权限由后端 API 安全层掌控
4. **绝对只读**：安全层强制拦截一切非 SELECT

---

## 2. 架构总览

```
用户 → agent-web (FastAPI :9000)
      → AgentWorkflow (graph/workflow.py)
      → AgentLoop (LLM function calling)
      → ToolRegistry
        ├── 9 个既有工具（第一优先，走 BreedingApiClient → api :8000）
        └── 【新增】run_sql_query 工具（兜底，走 SqlApiClient → api :8000）
              ↓
      api (FastAPI :8000) — 新增 POST /api/sql/query 端点
        ├── ① 只读校验（AST/正则拦截非 SELECT）
        ├── ② 强制 LIMIT（默认 100）
        ├── ③ 超时熔断（3s）
        └── ④ 参数化执行（asyncpg/SQLAlchemy text）
              ↓
      PostgreSQL 16（22 表，只读查询）
```

**关键点**：Agent 层 `pl_agent.agent` **保持不直连数据库**，遵循现有架构约束
（`agent` 无 FastAPI、无 DB 依赖，一切通过 `api` 层 HTTP 取数）。

---

## 3. 数据库层改动

### 3.1 现状

- 22 表（5 基础 + 17 扩展），数据量 < 2MB
- 表较多、关系复杂（pal → pal_stats / pal_skill / pal_passive / pal_drop / ...）

### 3.2 方案：暴露「宽表视图」给 Agent

按照 Text-to-SQL.md 的"进阶技巧"，表结构复杂时 Agent 写 SQL 容易出错。因此：

1. **创建视图 `v_pal_full`**：把帕鲁主表 + 关键关联表 JOIN 成一张宽表，
   覆盖 Agent 最可能问的长尾问题（按属性筛选、按被动/技能/掉落筛选、按体型/种族筛选等）。
2. 视图**只暴露给 SQL 工具**（Agent 提示词里只描述这一张宽表，不暴露 22 张原始表）。
3. 少量确实需要跨实体 JOIN 的场景（如"掉某物品的帕鲁"），可在宽表基础上
   再加 1-2 个辅助视图（如 `v_item_drop`、`v_skill_learn`）。

> **用普通 VIEW 而非物化视图（MATERIALIZED VIEW）**：数据量 < 2MB 且静态（仅重灌时变化），
> 普通视图查询时实时聚合开销可忽略，且**免去 seed 后的 REFRESH 维护**（物化视图若漏刷新会查到旧数据）。

**建议的宽表 `v_pal_full` 字段**（从现有 22 表提炼，覆盖高频长尾查询维度）：

| 列 | 来源表 | 说明 |
|----|--------|------|
| pal_id / game_id / cn_name / en_name | pal | 标识 |
| zukan_index / zukan_index_suffix | pal | 图鉴编号 |
| combi_rank / rarity / size / genus | pal | 配种/稀有度/体型/种族 |
| is_wild / egg / nocturnal / predator / summonable | pal | 生态特征 |
| best_work | pal | 最佳工种 |
| hp / melee_attack / shot_attack / defense | pal_stats | 基础属性 |
| run_speed / ride_sprint_speed | pal_stats | 速度 |
| capture_rate | pal_stats | 捕获率 |
| element_list | pal_element 聚合 | 元素（逗号拼接）|
| work_summary | work_suitability 聚合 | 工种汇总（如 "手工6/烧火4"）|
| passive_list | pal_passive + passive | 被动（逗号拼接中文名）|
| skill_count | pal_skill 聚合 | 可学技能数 |
| alias_list | pal_aliase 聚合 | 别名（逗号拼接，供按别名查询）|

> 无需刷新维护：普通视图每次查询实时聚合，数据重灌后自动反映最新数据。

### 3.3 SQL 落地文件

新增 `data/sql/004_text2sql.sql`（幂等，用 `CREATE OR REPLACE VIEW`——PG 不支持 `CREATE VIEW IF NOT EXISTS`）：
```sql
CREATE OR REPLACE VIEW v_pal_full AS
SELECT
    p.id AS pal_id, p.game_id, p.cn_name, p.en_name,
    p.zukan_index, p.zukan_index_suffix, p.combi_rank, p.rarity,
    p.is_wild, p.size, p.genus, p.egg, p.nocturnal, p.predator, p.summonable,
    p.best_work, p.image_url,
    s.hp, s.melee_attack, s.shot_attack, s.defense, s.run_speed,
    s.ride_sprint_speed, s.capture_rate,
    (SELECT string_agg(e.element_type, ',' ORDER BY e.element_type)
       FROM pal_element e WHERE e.pal_id = p.id) AS element_list,
    (SELECT string_agg(ws.work_type || ':' || ws.level, ' ' ORDER BY ws.level DESC)
       FROM work_suitability ws WHERE ws.pal_id = p.id) AS work_summary,
    (SELECT string_agg(pas.cn_name, ',' ORDER BY pas.cn_name)
       FROM pal_passive pp JOIN passive pas ON pas.id = pp.passive_id
      WHERE pp.pal_id = p.id) AS passive_list,
    (SELECT count(*) FROM pal_skill ps WHERE ps.pal_id = p.id) AS skill_count,
    (SELECT string_agg(pa.alias, ',' ORDER BY pa.alias)
       FROM pal_aliase pa WHERE pa.pal_id = p.id) AS alias_list
FROM pal p
LEFT JOIN pal_stats s ON s.pal_id = p.id;

-- 辅助视图：物品掉落来源（从掉落事实出发，避免 2433 个无掉落物品产生空行）
CREATE OR REPLACE VIEW v_item_drop AS
SELECT i.item_id, i.cn_name AS item_cn,
       p.cn_name AS pal_cn, p.game_id AS pal_game_id,
       d.rate, d.is_boss
FROM pal_drop d
JOIN item i ON i.id = d.item_id
JOIN pal p ON p.id = d.pal_id;

-- 辅助视图：帕鲁可学技能（命名避开已存在的 pal_skill 表）
CREATE OR REPLACE VIEW v_skill_learn AS
SELECT p.game_id, p.cn_name AS pal_cn,
       sk.waza_id, sk.cn_name AS skill_cn, sk.element, sk.power,
       ps.learn_level
FROM pal_skill ps
JOIN pal p ON p.id = ps.pal_id
JOIN skill sk ON sk.id = ps.skill_id;
```

---

## 4. API 层改动（安全执行器）

### 4.1 新增端点 `POST /api/sql/query`

位置：`packages/api/pl_agent/api/routes/sql_query.py`

```python
"""通用只读 SQL 查询端点 — Text-to-SQL 兜底的“安全执行器”。

设计遵循 Text-to-SQL.md 的四道防火墙：
  ① 只读校验：AST 解析拦截非 SELECT
  ② 强制 LIMIT：未写 LIMIT 自动追加（默认 100，上限 200）
  ③ 超时熔断：3 秒
  ④ 仅允许查询白名单视图（v_pal_full / v_item_drop / v_skill_learn）
"""
```

**请求/响应格式**：
```json
// 请求
{ "sql": "SELECT cn_name, combi_rank FROM v_pal_full WHERE rarity >= 10 ORDER BY combi_rank DESC LIMIT 5" }

// 响应（成功）
{ "success": true, "data": { "columns": ["cn_name","combi_rank"], "rows": [["空涡龙", 70], ...], "row_count": 5 } }

// 响应（失败）— 复用现有 format_error 格式，与 BreedingApiClient._request 的
// UpstreamEnvelope{success, data, error{code,message}} 校验兼容
{ "success": false, "error": { "code": "SQL_BLOCKED", "message": "只允许 SELECT 白名单视图" } }
```

> **错误码约定**：`SQL_BLOCKED`（非 SELECT/非白名单/多语句）、`SQL_SYNTAX`（sqlglot 解析失败）、
> `SQL_TIMEOUT`（3s 超时）、`SQL_ERROR`（执行异常）。
> Agent 侧 `BreedingApiClient._request` 收到 `success=false` 会抛 `UpstreamServiceError`，
> 工具 `run` 会转成 `ToolError` 返回给 LLM，LLM 应据错误信息修正 SQL 后重试。

### 4.2 安全执行器实现要点（四道防火墙）

| 防火墙 | 实现方式 | 位置 |
|--------|---------|------|
| **① 只读校验** | 用 `sqlglot.parse(sql, read="postgres")` 解析为 AST 列表：若 `len(parsed) != 1` 拒绝（天然拦截 `;` 多语句）；且该语句类型必须是 `Select`（或 `With` 内层为 Select）；拒绝 `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE` | `sql_query.py` |
| **② 白名单表** | AST 提取 FROM 引用的表名，必须在 `{v_pal_full, v_item_drop, v_skill_learn}` 白名单内 | `sql_query.py` |
| **③ 强制 LIMIT** | 用 AST 修改 limit 子句（`expression.limit(100)`），再 `transpile(read="postgres")` 回方言；不用字符串拼接（避免破坏语法/引号）。无 LIMIT → 加 `LIMIT 100`；有则 min(用户值, 200)；同时限制 `OFFSET`（避免深翻页全表扫描），如 `OFFSET + LIMIT ≤ 500` | `sql_query.py` |
| **④ 超时熔断** | `asyncio.wait_for(..., timeout=3)`；连接使用现有 `create_engine_and_sessionmaker`，`execution_options` 不额外配置（用超时兜底） | `sql_query.py` |

**依赖**：新增 `sqlglot` 到 `packages/api/pyproject.toml`。

### 4.3 注册路由

在 `packages/api/pl_agent/api/main.py` 中 `include_router(sql_query_router)`。

### 4.4 白名单视图 DDL 注入提示词

安全层从数据库 `information_schema` 或固定配置读取视图 DDL，提供给 Agent 提示词
（见第 5 节）。

---

## 5. Agent 层改动

### 5.1 新增工具 `run_sql_query`

位置：`packages/agent/pl_agent/agent/tools/sql_query.py`

```python
class RunSqlQueryTool(Tool):
    """长尾问题兜底：把自然语言问题转成 SQL 查宽表。

    仅当既有 9 个工具无法覆盖时才使用。执行前会经过后端只读安全层，
    只允许 SELECT 且强制 LIMIT。"""
    name = "run_sql_query"
    description = (
        "当用户提问超出配种/工种/技能/被动/物品等常规工具范围时，"
        "把问题翻译成 SQL 查询宽表 v_pal_full（帕鲁全量宽表）"
        "或 v_item_drop（掉落）/ v_skill_learn（技能）。"
        "只写 SELECT，不写其他语句，记得加 LIMIT。"
        "例：'哪些帕鲁体型是 L 且速度超过 7000' → "
        "SELECT cn_name, size, run_speed FROM v_pal_full WHERE size='L' AND run_speed > 7000 LIMIT 20"
    )
    parameters = {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "只读 SELECT 语句，查询白名单视图",
            }
        },
        "required": ["sql"],
    }
```

### 5.2 新增客户端方法

`BreedingApiClient`（或新建 `SqlApiClient`）增加：
```python
async def run_sql_query(self, sql: str) -> dict:
    return await self._request("POST", "/api/sql/query", json={"sql": sql})
```
> 复用一个 HTTP client，避免新建连接层。

### 5.3 注册到 ToolRegistry

在 `build_breeding_tools()` 中追加：
```python
from .sql_query import RunSqlQueryTool
# ...
tools.append(RunSqlQueryTool(client))
```

### 5.4 提示词注入：数据库结构（宽表 DDL）

在 `assistant.md` 或运行时注入中，追加【数据库宽表（Text-to-SQL 兜底）】段：

```text
【数据库宽表（仅当常规工具无法覆盖时使用 run_sql_query 查询）】
表 v_pal_full（帕鲁全量宽表，1 行 = 1 只帕鲁）：
- pal_id INTEGER, game_id TEXT, cn_name TEXT, en_name TEXT
- zukan_index INTEGER, combi_rank INTEGER, rarity INTEGER
- size TEXT（XS/S/M/L/XL）, genus TEXT（种族）
- nocturnal BOOLEAN, predator BOOLEAN, summonable BOOLEAN
- egg TEXT, best_work TEXT
- hp / melee_attack / shot_attack / defense INTEGER
- run_speed / ride_sprint_speed INTEGER, capture_rate NUMERIC
- element_list TEXT（逗号分隔元素）, work_summary TEXT（如 "手工6/烧火4"）
- passive_list TEXT（逗号分隔被动）, skill_count INTEGER

表 v_item_drop（物品掉落来源）：item_id, item_cn, pal_cn, rate, is_boss
表 v_skill_learn（帕鲁可学技能）：game_id, pal_cn, skill_cn, element, power, learn_level

用法：只用 SELECT，必须 LIMIT（建议 20-50）。只查这三张白名单视图。

注意：
- 数值字段（hp/run_speed/capture_rate 等）可能为 NULL（无 stats 数据的帕鲁），
  按数值筛选时用 IS NOT NULL 或容忍漏行。
- 通常用 cn_name / game_id / element_list / passive_list 等可读字段查询，
  避免用 pal_id（内部自增 ID）作为用户可感知的标识。
- 若 run_sql_query 报错，根据错误信息修正 SQL（检查表名/字段名/WHERE 语法/LIMIT）后重试，最多重试 2 次。
```

> 提示词长度可控（3 张视图 + 字段名，约 500-800 字符）。

### 5.5 触发策略（重要）

在 `assistant.md` 中明确**工具优先级**，避免 SQL 工具被滥用：

```text
【工具优先级】
1. 配种/工种/技能/被动/物品/详情/统计 → 先用 9 个常规工具（精准、参数化）
2. 常规工具无法覆盖的查询类长尾问题（如按体型/种族/属性筛选、跨维度统计）
   → 用 run_sql_query
3. 玩法知识（怎么抓/怎么骑乘）→ 直接基于通用知识回答，不用 SQL
```

同时在 `AgentLoop` 或 workflow 中**不强制**开关（由提示词引导）；
若后续需要更硬的控制，可在 `config.py` 的 `Settings` 增加 `enable_text2sql: bool = True`，
并在 `build_breeding_tools()` 中按开关决定是否注册 `RunSqlQueryTool`。

---

## 6. 前端改动

### 6.1 可选：SQL 结果卡片

若需要把 SQL 查询结果以表格形式展示给用户（增强可信度），数据流如下：

1. `run_sql_query` 工具返回 `{columns, rows, row_count}`（来自 `/api/sql/query` 的 `data`）
2. `presenter.py` 的 `_DATA_CARD_TOOL_TYPES` 增加 `"run_sql_query": "table"`，
   `build_data_cards` 透传 `{type:"table", columns, rows}`
3. 前端新增 `TableCard` 组件，按 `columns` 渲染表头、`rows` 渲染单元格

> MVP 阶段 LLM 直接用文本总结查询结果即可，卡片渲染作为 P2 增强。

---

## 7. 安全设计复查（对照文档四道防火墙）

| 文档要求 | 本项目实现 | 状态 |
|---------|-----------|------|
| 强制只读（拦截 DELETE/UPDATE/DROP/ALTER/INSERT） | `sqlglot` AST 校验，仅允许 SELECT + 白名单视图 | 计划 |
| 连接从库（Slave DB） | 数据量 < 2MB、单实例部署；**用白名单视图 + 只读校验替代**，风险等价 | 说明 |
| 强制截断（LIMIT） | 默认 LIMIT 100，上限 200 | 计划 |
| 超时熔断 | `asyncio.wait_for` 3s | 计划 |

> **关于从库**：当前单库部署且数据量极小（<2MB），无读写锁表风险。
> 若未来接入大库/主从架构，可在 `sql_query.py` 用独立只读 engine 指向从库，
> 代码预留 `SQL_READ_ONLY_URL` 环境变量支持。

---

## 8. 测试计划

### 8.1 单元测试（api 层）

新增 `packages/api/pl_agent/api/__tests__/test_sql_query.py`：

| 用例 | 断言 |
|------|------|
| `test_select_allowed` | `SELECT * FROM v_pal_full LIMIT 5` → 200 且 row_count ≤ 5 |
| `test_delete_blocked` | `DELETE FROM v_pal_full` → 4xx 且 SQL 不执行 |
| `test_drop_blocked` | `DROP TABLE v_pal_full` → 4xx |
| `test_update_blocked` | `UPDATE ...` → 4xx |
| `test_multi_statement_blocked` | `SELECT 1; DROP TABLE x` → 4xx |
| `test_non_whitelist_table_blocked` | `SELECT * FROM pal` → 4xx（只允许白名单视图）|
| `test_missing_limit_auto_append` | 无 LIMIT → 自动 LIMIT 100 |
| `test_limit_capped_at_200` | `LIMIT 9999` → 被钳制到 200 |
| `test_timeout` | 慢查询 → 超时报错（mock）|
| `test_sql_returns_columns_rows` | 响应含 columns + rows |
| `test_sql_syntax_error_returns_json` | 非法 SQL → `{success:false, error.code=SQL_SYNTAX}`（而非 500）|
| `test_limit_rewritten_correctly` | 无 LIMIT 的 SQL 经 AST 改写后 row_count ≤ 100 且语法有效 |

### 8.2 Agent 层测试

新增 `packages/agent/pl_agent/agent/tools/__tests__/test_sql_query_tool.py`：
- `test_tool_registered`：`run_sql_query` 在 build_breeding_tools 返回列表中
- `test_tool_calls_client`：tool.run 正确调用 client.run_sql_query
- `test_description_mentions_readonly`：description 强调只读 + LIMIT

### 8.3 集成/浏览器验证

- `tests/integration/`：api 端点 + agent 工具联调
- 浏览器验证长尾问题（如"哪些帕鲁体型是 L 且跑得快""按种族统计有多少只"）

---

## 9. 实施步骤（分阶段）

### P0：安全执行器（api 层）
- [ ] 新增 `data/sql/004_text2sql.sql`（3 个普通视图）+ 应用
- [ ] 新增 `routes/sql_query.py`（四道防火墙）
- [ ] `pyproject.toml` 加 `sqlglot`
- [ ] 注册路由 + 单元测试

### P1：Agent 工具接入
- [ ] 新增 `tools/sql_query.py`（RunSqlQueryTool）
- [ ] client 增加 `run_sql_query`
- [ ] 注册到 `build_breeding_tools`
- [ ] assistant.md 注入宽表 DDL + 工具优先级
- [ ] Agent 层测试

### P2：前端增强（可选）
- [ ] presenter 增加 table 卡片
- [ ] 前端 TableCard 组件

### P3：回归与部署
- [ ] `make test-all` 全量回归
- [ ] 重建 api + agent-web 镜像
- [ ] 浏览器端到端验证长尾问题
- [ ] 提交代码（沙箱连不上 GitHub，需用户终端 push）

---

## 10. 风险与注意事项

1. **LLM 写 SQL 准确率**：通过宽表 + 明确字段名 + 示例降错；若仍不理想，
   可在提示词中追加 1-2 条**经典示例 SQL**（few-shot）。
2. **SQL 工具滥用**：提示词明确"常规工具优先"，防止 Agent 遇到常规问题也走 SQL。
3. **视图维护**：采用普通 VIEW，无 REFRESH 负担；数据重灌（seed）后自动反映最新数据。
4. **sqlglot 依赖**：新增第三方依赖，需在 `packages/api` 的 uv 环境安装
   （`uv add sqlglot`）并确保 Docker 镜像安装。
5. **不要暴露原始 22 表**：Agent 只看到 3 个宽表视图，减少写错 SQL 概率，
   也缩小攻击面。

---

## 11. 文档关联

- 方案依据：[Text-to-SQL.md](../../context/Text-to-SQL.md)
- 表结构：[DATABASE_DESIGN_TCIMBA_V2.md](../design/DATABASE_DESIGN_TCIMBA_V2.md)
- 架构：[PROJECT_STRUCTURE.md](../design/PROJECT_STRUCTURE.md)、[ARCHITECTURE.md](../archive/ARCHITECTURE.md)
