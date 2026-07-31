# 数据库规范化迁移 — 开发计划

> 基于: `docs/architecture/DATABASE_DESIGN.md` v1.1 | 日期: 2026-07-31

---

## 变更概览

| 维度 | 当前 (宽表) | 目标 (5 表规范化) |
|------|------------|------------------|
| 表数量 | 1 (`pals`) | 5 (`pal`, `pal_aliase`, `pal_element`, `work_suitability`, `breeding_rule`) |
| 工作适应性 | 12 列 (每列一个索引) | 独立表 + 1 个复合索引 |
| 元素 | JSONB `elements` | `pal_element` 行 |
| 别名 | JSONB `aliases` | `pal_aliase` 行 |
| PK 类型 | TEXT (game_id) | SERIAL (id) + UNIQUE game_id |
| 配种规则 | 代码硬编码 | `breeding_rule` 表 |
| 配种 SQL | `FROM pals a, pals b WHERE {col}>=...` | `JOIN work_suitability` |

---

## Phase 1 — 迁移 SQL

**文件**: `data/sql/002_normalize.sql`

**产出**: 一个事务脚本，包含:
1. `CREATE TABLE` 5 张新表
2. `INSERT INTO ... SELECT` 从旧 `pals` 迁移数据
3. 宽列 `handiwork/kindling/...` → `work_suitability` 行 (12 行/帕鲁)
4. `JSONB elements` → `pal_element` 行
5. `JSONB aliases` → `pal_aliase` 行
6. 建索引
7. `DROP TABLE pals; ALTER TABLE pal RENAME TO pals;` (保持旧表名兼容过渡)

**风险**: 不可逆操作。执行前 `pg_dump` 备份。

---

## Phase 2 — schema.py (数据模型)

**文件**: `packages/core/pl_agent/core/schema.py`

**变更**: **Pal 扁平面向业务层不变**。`Pal` dataclass 保持现有结构——它是 API 和业务逻辑的内部表示。数据库规范化不影响 `Pal` 的 Python 形态。

新增两个轻量 dataclass 用于 DB 读写:

```python
@dataclass
class PalRow:
    """pal 表行 — 不含子表数据"""
    id: int
    game_id: str
    zukan_index: int
    cn_name: str
    en_name: str
    combi_rank: int
    rarity: int
    is_wild: bool
    image_url: str | None
    wiki_url: str | None

@dataclass
class BreedingRuleRow:
    """breeding_rule 表行"""
    id: int
    child_id: int
    parent_a_id: int | None
    parent_b_id: int | None
    rule_type: str  # fixed_pair / same_species / unbreedable
    description: str | None
```

`WorkSuitability` 不变——仍是 12 个 int 字段的 dataclass，在 adapter 层做行↔对象转换。

---

## Phase 3 — Postgres Adapter (写入)

**文件**: `packages/adapters/adapters/postgres/adapter.py`

**变更**: 重写 `UPSERT_PAL` 为多表事务写入:

```
Pal (业务对象)
  │
  ├── 1. INSERT INTO pal (...) ON CONFLICT (game_id) DO UPDATE
  │      返回 pal.id
  │
  ├── 2. DELETE + INSERT pal_element (属性 1-2 行)
  │
  ├── 3. DELETE + INSERT pal_aliase (别名 0-N 行)
  │
  └── 4. UPSERT work_suitability (12 行, level>=0)
         INSERT ... ON CONFLICT (pal_id, work_type) DO UPDATE
```

`upsert_all(pals)` 不变，内部逐条调用新的 `upsert_pal(pal)`。

---

## Phase 4 — Postgres Loader (读取)

**文件**: `packages/adapters/adapters/postgres/loader.py`

**变更**: 核心改动——加载逻辑从单表 SELECT 变为多表 JOIN 拼接:

### `load_all()` (替代 `load_hot()`)

```sql
-- 一条查询拼装完整 Pal 列表
SELECT
    p.id, p.game_id, p.zukan_index, p.cn_name, p.en_name,
    p.combi_rank, p.rarity, p.is_wild, p.image_url, p.wiki_url,
    array_agg(pe.element_type) FILTER (WHERE pe.element_type IS NOT NULL) AS elements,
    coalesce(jsonb_object_agg(ws.work_type, ws.level)
             FILTER (WHERE ws.work_type IS NOT NULL), '{}') AS work_suitability_json,
    array_agg(pa.alias) FILTER (WHERE pa.alias IS NOT NULL) AS aliases
FROM pal p
LEFT JOIN pal_element pe ON p.id = pe.pal_id
LEFT JOIN work_suitability ws ON p.id = ws.pal_id
LEFT JOIN pal_aliase pa ON p.id = pa.pal_id
GROUP BY p.id
ORDER BY p.combi_rank;
```

然后在 Python 侧装配 `Pal` 对象:
- `element_type[]` → `list[Element]`
- `work_suitability_json` → `WorkSuitability.from_dict()`

### `get_detail(pal_id)` — 不变，仍查 `pal` 表

### `query_suitability(work_type, min_level, limit)` — **简化**:

```sql
-- 之前: SELECT id, cn_name, {work_type} AS lv FROM pals WHERE {work_type} >= $1
-- 现在: 直接查 work_suitability + JOIN pal
SELECT p.id, p.cn_name, p.combi_rank, ws.level
FROM work_suitability ws
JOIN pal p ON ws.pal_id = p.id
WHERE ws.work_type = $1 AND ws.level >= $2
ORDER BY ws.level DESC
LIMIT $3;
```

**安全改进**: 不再有动态列名插值（之前是 SQL 注入风险点）。

### 删除 `BreedingIndex`

不需要单独的索引 dataclass——启动时直接加载 `list[Pal]` 到内存，Parser 构建索引。

---

## Phase 5 — API Routes (SQL 重写)

**文件**: `packages/api/pl_agent/api/routes/query.py`

### 变更明细

#### `BREED_PARENTS_SQL`

```sql
-- 之前
SELECT a.cn_name, a.id, a.combi_rank, a.is_wild,
       b.cn_name, b.id, b.combi_rank, b.is_wild
FROM pals a, pals b
WHERE round((a.combi_rank + b.combi_rank) / 2.0) = $1
  AND a.id != $2 AND b.id != $2 AND a.id <= b.id

-- 之后 (仅表名从 pals 变 pal，列名不变)
SELECT a.cn_name, a.id, a.combi_rank, a.is_wild,
       b.cn_name, b.id, b.combi_rank, b.is_wild
FROM pal a, pal b
WHERE round((a.combi_rank + b.combi_rank) / 2.0) = $1
  AND a.id != $2 AND b.id != $2 AND a.id <= b.id
```

> `$2` 现在是 `pal.id` (SERIAL)，不再混用 game_id。

#### `SUITABILITY_SQL` — **最大改动**

```sql
-- 之前 (动态列插值 — 不安全)
SELECT id, cn_name, number, combi_rank, is_wild, handiwork, kindling, ...
FROM pals WHERE {col} >= $1 ORDER BY {col} DESC LIMIT $2

-- 之后 (参数化 JOIN)
SELECT p.id, p.cn_name, p.number, p.combi_rank, p.is_wild, ws.level
FROM pal p
JOIN work_suitability ws ON p.id = ws.pal_id
WHERE ws.work_type = $1 AND ws.level >= $2
ORDER BY ws.level DESC
LIMIT $3
```

**收益**: 消除 `f-string` 动态列名插值，彻底解决 SQL 注入风险。

#### `WORK_STATS_SQL` — **大幅简化**

```sql
-- 之前 (12 路 UNION ALL)
SELECT 'handiwork' AS wt, max(handiwork), avg(handiwork),
       count(*) FILTER (WHERE handiwork>0) FROM pals
UNION ALL
SELECT 'kindling', max(kindling), avg(kindling),
       count(*) FILTER (WHERE kindling>0) FROM pals
UNION ALL ...

-- 之后 (一条 GROUP BY)
SELECT work_type,
       max(level) AS max_level,
       ROUND(avg(level), 1) AS avg_level,
       count(*) FILTER (WHERE level > 0) AS pal_count
FROM work_suitability
GROUP BY work_type
ORDER BY max_level DESC;
```

**收益**: 12 路 UNION ALL → 1 个 GROUP BY，SQL 从 ~60 行缩小到 ~10 行。

#### `_pal_row_to_dict()` — 适配新行结构

不再从宽列构建 `work_suitability`，改为从 JOIN 结果构建。

#### `_breeding_query()` — 增加守卫

```python
async def _breeding_query(pool, pal_id: int, combi_rank: int):
    # 第 0 步: 查特殊规则
    rules = await pool.fetch(
        "SELECT rule_type, parent_a_id, parent_b_id FROM breeding_rule WHERE child_id = $1",
        pal_id
    )
    for r in rules:
        if r["rule_type"] == "unbreedable":
            return []  # 不可配种
        if r["rule_type"] == "same_species":
            return [ParentPair(...)]  # 同类繁殖
        if r["rule_type"] == "fixed_pair":
            ...  # 固定组合

    # 第 1 步: 公式
    rows = await pool.fetch(BREED_PARENTS_SQL, combi_rank, pal_id)
    return [ParentPair(...) for r in rows]
```

---

## Phase 6 — main.py (启动逻辑)

**文件**: `packages/api/pl_agent/api/main.py`

**变更**: 最小改动:

1. `PostgresLoader.load_hot()` → `PostgresLoader.load_all()` (返回 `list[Pal]`)
2. 删除 `BreedingIndex` 概念——直接用 `list[Pal]` 传给 `QueryParser`
3. `QueryParser(all_pals)` — 内部构建自己的索引
4. PG 降级路径不变

```python
# 之前
index = await pg_loader.load_hot()       # → BreedingIndex
all_pals = index.pals
parser = QueryParser(all_pals)

# 之后
pals = await pg_loader.load_all()        # → list[Pal]
parser = QueryParser(pals)
```

---

## Phase 7 — data_loader.py (JSON 降级)

**文件**: `packages/core/pl_agent/core/data_loader.py`

**变更**: 极小改动。JSON 文件 (`pal_data.json`) 格式不变——Pal 扁平面向文件存储仍然合理。仅在 JSON → Pal 反序列化时确保 `elements`、`work_suitability` 正确映射。

---

## Phase 8 — paldb adapter/parser (数据采集)

**文件**: `packages/adapters/adapters/paldb/adapter.py`

**变更**: 不需要改动。爬虫采集的是扁平的 `Pal` 对象，写入 PG 时由 PostgresAdapter 负责拆表。adapter 只需输出 `list[Pal]`，不关心最终存储结构。

---

## 实施顺序

```
Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4 ──▶ Phase 5 ──▶ Phase 6 ──▶ Phase 7
 (SQL)     (schema)   (adapter)   (loader)    (routes)    (main)     (fallback)
                                      │
                                      └── Phase 3+4 可并行 ──┘
                                                    │
                                              Phase 8 (验证)
```

| Phase | 依赖 | 可并行 | 风险 |
|:---:|------|:---:|------|
| 1 | 无 | - | 🔴 不可逆数据迁移 |
| 2 | 无 | ✅ Phase 1 | 🟡 schema 加字段不破坏现有 |
| 3 | 1, 2 | ✅ Phase 4 | 🟡 UPSERT 逻辑需验证 |
| 4 | 1, 2 | ✅ Phase 3 | 🟡 JOIN 查询性能 |
| 5 | 4 | ❌ 依赖 loader | 🟡 SQL 重写需逐条验证 |
| 6 | 4 | ❌ | 🟢 仅改 3 行 |
| 7 | 无 | ✅ 全部 | 🟢 JSON 格式不变 |

## 验证清单

- [ ] `002_normalize.sql` 在本地 PG 执行成功，数据无丢失
- [ ] `PostgresWriter.upsert_all()` 写入 288 条 Pal，5 表行数正确
- [ ] `PostgresLoader.load_all()` 返回 `list[Pal]`，work_suitability 正确
- [ ] `POST /api/query {"input": "墨罗娜"}` 返回父母对 (22 对)
- [ ] `POST /api/query {"input": "手工:6"}` 返回候选列表
- [ ] `GET /api/suitability/stats` 12 工种统计正确
- [ ] `GET /health` pals_loaded=288
- [ ] PG 不可用时 JSON 降级正常 (make serve 无 PG)
- [ ] 现有 63 个测试全部通过
