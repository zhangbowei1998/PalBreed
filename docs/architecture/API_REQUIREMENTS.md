# API 服务需求文档

> 版本: v2.0 | 日期: 2026-08-04 | 状态: 重构完成 — 引擎层已移除，SQL 直连

---

## 目录

1. [概述与定位](#1-概述与定位)
2. [API 设计原则](#2-api-设计原则)
3. [端点规格](#3-端点规格)
4. [智能查询路由](#4-智能查询路由)
5. [响应模型](#5-响应模型)
6. [错误处理](#6-错误处理)
7. [配种查询实现](#7-配种查询实现)
8. [前端对接契约](#8-前端对接契约)
9. [验收标准](#9-验收标准)

---

## 1. 概述与定位

### 1.1 定位

API 层是所有业务逻辑的**承载者**。路由直接通过 PostgreSQL SQL 实现配种查询和属性筛选：

1. 接收 HTTP 请求
2. 执行 PostgreSQL SQL 查询
3. 格式化响应

### 1.2 与 NLU 的关系

当前版本（v0.1）**跳过 NLU**，API 直接接收半结构化输入。后续 v0.2 可在 API 前加 NLU 层，不改变 API 本身。

```
v0.1 (当前):   用户 ──▶ API ──▶ 引擎
v0.2 (未来):   用户 ──▶ NLU ──▶ API ──▶ 引擎
```

### 1.3 技术选型

| 项 | 选择 |
|----|------|
| 框架 | FastAPI |
| 异步 | 内置 async/await |
| 文档 | 自动生成 Swagger (`/docs`) |
| CORS | 全开（开发阶段） |
| 数据加载 | PG 全量加载 pals (Parser 索引) + SQL 直查；PG 不可用时 JSON 降级 |

---

## 2. API 设计原则

1. **一个智能入口**：用户不需要选择端点，一个端点自动判断查询类型
2. **精确也有，快捷也有**：结构化查询（`工种:等级`）和名称直查（`帕鲁名`）用同一输入框
3. **一级父母对**：配种查询返回目标帕鲁的所有父母组合，用户点击父代继续查询
4. **前端友好**：响应包含前端可直接渲染的文本 + 结构化数据
5. **中文原生**：工种接受中英文，帕鲁名接受中英别名

---

## 3. 端点规格

### 3.1 端点总览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/query` | 🔑 智能查询（唯一主要入口） |
| `GET` | `/api/pal/{pal_id}` | 帕鲁详情 |
| `GET` | `/api/breeding/tree/{pal_id}` | 获取父母对列表 (一级) |
| `GET` | `/api/suitability/stats` | 全工种统计 |
| `GET` | `/health` | 健康检查 |

### 3.2 POST `/api/query` — 智能查询

**这是唯一的用户查询入口。** API 自动判断输入类型。

#### 请求

```json
{
  "input": "阿努比斯",
  "max_depth": 5
}
```

```json
{
  "input": "手工:6",
  "max_depth": 5
}
```

```json
{
  "input": "handiwork:6",
  "max_depth": 5
}
```

```json
{
  "input": "handiwork:6,mining:5",
  "max_depth": 5
}
```

#### 输入自动识别规则

```
API 解析 input 字段, 按优先级判断:

1. 是否含 ":" ？
   → 是: 解析为 suitability_query (属性查询)
     格式: "工种:等级"  例: "手工:6"  "handiwork:3"  "handiwork:3,mining:3"
   → 否: 继续下一步

2. 是否为已知工种关键词？(不含冒号的纯中文/英文工种名)
   → 是: suitability_query, level 默认为 1
     例: "手工"  "handiwork"  "采矿"
   → 否: 继续下一步

3. 名称匹配 (中文/英文/别名/编号) → name_query (名称直查)
   例: "阿努比斯"  "Anubis"  "狗头"  "139"

4. 模糊匹配？(前缀子串匹配, 编辑距离 ≤ 2 的相似名)
   → 有候选: 返回候选列表 + "您是指?"
   → 无候选: 返回 404 + 搜索提示
```

#### 响应 — 名称直查（返回父母对列表）

```json
{
  "type": "name_query",
  "query": "阿努比斯",
  "pal": {
    "id": "Anubis",
    "number": 139,
    "cn_name": "阿努比斯",
    "elements": ["Earth"],
    "combi_rank": 480,
    "work_suitability": {"handiwork": 6, "mining": 6, "transporting": 4}
  },
  "parent_pairs": [
    {"parent_a": "棉悠悠", "parent_b": "捣蛋猫", "child_rank": 480},
    {"parent_a": "雷隐鹿", "parent_b": "烽歌龙", "child_rank": 480}
  ],
  "total_pairs": 5,
  "display_text": "🥚 父母组合 (5 对):\n  1. 棉悠悠 + 捣蛋猫\n  ..."
}
```

> 注: 以上数据为示例, 非真实游戏数据。

#### 响应 — 属性查询（先返候选列表）

```json
{
  "type": "suitability_query",
  "query": "handiwork:6",
  "result_type": "candidates",
  "candidates": [
    {
      "pal": {"id": "Anubis", "cn_name": "阿努比斯", "number": 139},
      "matched_level": 6,
      "all_suitabilities": {"handiwork": 6, "mining": 6, "transporting": 4}
    }
  ],
  "total": 1,
  "hint": "请选择目标帕鲁，发送 POST /api/query {\"input\": \"阿努比斯\"}"
}
```

#### 属性查询 — 超出范围

```json
{
  "type": "suitability_query",
  "query": "handiwork:10",
  "result_type": "out_of_range",
  "max_available": 6,
  "candidates": [],
  "message": "手工最高等级为 Lv6，已为您展示所有手工帕鲁",
  "fallback_candidates": [
    {"pal": {"id": "Anubis", "cn_name": "阿努比斯"}, "matched_level": 6},
    {"pal": {"id": "Lyleen", "cn_name": "百合女王"}, "matched_level": 5}
  ],
  "total": 2
}
```

### 3.3 GET `/api/pal/{pal_id}` — 帕鲁详情

```
GET /api/pal/Anubis
```

```json
{
  "id": "Anubis",
  "number": 139,
  "cn_name": "阿努比斯",
  "en_name": "Anubis",
  "combi_rank": 480,
  "elements": ["Earth"],
  "rarity": 10,
  "is_wild": true,
  "work_suitability": {"handiwork": 6, "mining": 6, "transporting": 4}
}
```

### 3.4 GET `/api/breeding/tree/{pal_id}` — 获取父母对

返回目标帕鲁的所有可配种父母组合 (ParentPair 列表)，由 SQL CROSS JOIN 计算得出。

### 3.5 GET `/api/suitability/stats` — 全工种统计

```json
{
  "handiwork": {"max_level": 6, "avg_level": 2.1, "count": 85},
  "mining": {"max_level": 6, "avg_level": 1.8, "count": 62},
  ...
}
```

---

## 4. 智能查询路由

### 4.1 输入解析流程

```
用户输入: "手工:6"
     │
     ▼
┌─────────────────┐
│ 1. 是否含 ":" ？ │── 是 ──▶ 解析为 suitability_query
└────────┬────────┘
         │ 否
         ▼
┌──────────────────┐
│ 2. 中文名/英文名/ │── 是 ──▶ name_query → SQL 配种查询
│    别名精确匹配？  │
└────────┬─────────┘
         │ 否
         ▼
┌──────────────────┐
│ 3. 模糊匹配？     │── 有候选 ──▶ 返回候选列表 + "您是指?"
└────────┬─────────┘
         │ 无
         ▼
     404 + 搜索提示
```

### 4.2 工种的输入格式

接受三种格式（统一归一化为英文字段名）：

```
"手工:6"      → {work_type: "handiwork", level: 6}
"手工作业:3"  → {work_type: "handiwork", level: 3}
"handiwork:3" → {work_type: "handiwork", level: 3}
"手工"         → {work_type: "handiwork", level: 1}  (默认最低等级1)
```

多条件查询：

```
"手工:3,采矿:3"            → [{work_type: "handiwork", level: 3}, {work_type: "mining", level: 3}]
"手工:3, 采矿:3"            → 同上 (逗号前后空格的容错)
"handiwork:3,mining:3"     → 同上
```

解析规则: 按逗号分割, 去除每段前后空格, 每段独立解析为 `工种:等级`。
至少需要一个有效条件, 全无效则返回 `INVALID_INPUT`。

中文工种关键词 → 内部字段映射：

```
手工/手工作业    → handiwork      生火/烧火/点火      → kindling
浇水/灌溉       → watering       播种/种植/种地       → planting
发电/电力/充电  → generating_electricity     采集/收获 → gathering
伐木/砍树       → lumbering      采矿/挖矿           → mining
冷却/降温       → cooling        制药/医药           → medicine
搬运/运输       → transporting   牧场/放牧           → farming
```

### 4.3 帕鲁名称匹配

匹配时统一做 `casefold()` 处理 (大小写不敏感)。

优先级：
1. 精确匹配 `cn_name`（中文官方名, casefold）
2. 精确匹配 `en_name`（英文图鉴名, casefold）
3. 精确匹配 `id`（内部英文 ID, casefold）
4. 精确匹配 `aliases` 中任意一个（别称, casefold）
5. 精确匹配 `number`（图鉴编号）— 用户输入纯数字如 "139"
6. 子串包含匹配（前缀优先: "阿努" 可匹配 "阿努比斯"）

---

## 5. 响应模型

### 5.1 统一响应格式

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

失败时：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "PAL_NOT_FOUND",
    "message": "未找到帕鲁: xxx",
    "suggestions": ["阿努比斯", "焰皇"]
  }
}
```

### 5.2 错误码

| 错误码 | HTTP | 说明 |
|--------|:---:|------|
| `PAL_NOT_FOUND` | 404 | 帕鲁名不匹配 |
| `INVALID_WORK_TYPE` | 400 | 工种名不合法 |
| `INVALID_INPUT` | 400 | 输入格式错误 |
| `NO_BREEDING_PATH` | 200 | 无配种路径 (正常业务结果，result_type="no_path") |
| `INTERNAL_ERROR` | 500 | 服务内部错误 |

---

## 6. 错误处理

### 6.1 帕鲁找不到

```json
{
  "success": false,
  "error": {
    "code": "PAL_NOT_FOUND",
    "message": "未找到帕鲁 '阿奴比斯'",
    "suggestions": ["阿努比斯"]
  }
}
```

`suggestions` 通过模糊匹配（前缀匹配、编辑距离）生成，不超过 5 条。

### 6.2 工种不合法

```json
{
  "success": false,
  "error": {
    "code": "INVALID_WORK_TYPE",
    "message": "未知工种: '打铁'",
    "valid_types": ["手工", "生火", "浇水", "播种", "发电", "采集", "伐木", "采矿", "冷却", "制药", "搬运", "牧场"]
  }
}
```

### 6.3 无配种路径

```json
{
  "success": true,
  "data": {
    "type": "name_query",
    "pal": { "id": "Frostallion", "cn_name": "唤冬兽" },
    "parent_pairs": [],
    "total_pairs": 0,
    "message": "唤冬兽仅可通过同类繁殖或野外捕获"
  }
}
```

---

## 7. 配种查询实现

### 7.1 启动时初始化

```python
# 优先从 PostgreSQL 加载 pals
try:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM pals")
        pals = [parse_pal_row(row) for row in rows]
except Exception:
    # PG 不可用: JSON 降级
    pals = DataLoader().load("data/processed/pal_data.json")

# 创建 Parser 索引
parser = QueryParser(pals)
```

### 7.2 请求处理管线

```
POST /api/query  {"input": "手工:6"}
  │
  ├── 1. 输入解析 (Parser)
  │      "手工:6" → {type: "suitability", work_type: "handiwork", level: 6}
  │
  ├── 2. SQL 属性筛选
  │      SELECT cn_name FROM pals WHERE handiwork >= 6 ORDER BY handiwork DESC
  │
  ├── 3. 格式化响应
  └── 4. 返回候选列表
```

```
POST /api/query  {"input": "阿努比斯"}
  │
  ├── 1. 名称匹配 → Pal
  │
  ├── 2. 执行 SQL 配种查询 (CROSS JOIN)
  │
  ├── 3. 格式化响应
  └── 4. 返回父母对列表
```

### 7.3 配种 SQL

```python
BREED_PARENTS_SQL = """
    SELECT a.cn_name AS parent_a, b.cn_name AS parent_b
    FROM pals a, pals b
    WHERE round((a.combi_rank + b.combi_rank) / 2.0) = $1
      AND a.id != $2 AND b.id != $2
      AND a.id <= b.id
"""
```

---

## 8. 前端对接契约

### 8.1 前端只需要调两个接口

| 场景 | 调什么 |
|------|--------|
| 用户输入任何内容 | `POST /api/query` |
| 查看帕鲁详情 | `GET /api/pal/{id}` |

### 8.2 前端交互流程

```
用户输入 ──▶ POST /api/query
               │
               ├── type: "name_query" ──▶ 渲染父母对列表
               │
               ├── type: "suitability_query",
               │    result_type: "candidates"
               │    ──▶ 渲染候选列表
               │        用户点击某个帕鲁 ──▶ POST /api/query {"input": "阿努比斯"}
               │                             ──▶ 渲染该帕鲁的父母对
               │
               └── type: "suitability_query",
                    result_type: "out_of_range"
                    ──▶ 显示提示 + fallback 列表
```

### 8.3 display_text 格式约定

API 返回的 `display_text` 由以下规则生成:

```
父母对格式:
  "🥚 父母组合 ({count} 对):
   1. {parent_a} + {parent_b}
   2. {parent_a} + {parent_b}
   ..."

示例:

```
🥚 父母组合 (22 对):
  1. 织夜鹿 + 燎火舞伶
  2. 霹雳犬 + 遁地鼠
  ...
```

---

## 9. 验收标准

### 9.1 名称直查

- [x] `POST /api/query {"input": "阿努比斯"}` 返回所有父母对
- [x] `POST /api/query {"input": "Anubis"}` 返回相同结果
- [x] `POST /api/query {"input": "anubis"}`（大小写）也能匹配
- [x] `POST /api/query {"input": "不存在的帕鲁"}` 返回 404 + 建议

### 9.2 属性查询

- [x] `POST /api/query {"input": "手工:6"}` 返回候选列表含阿努比斯
- [x] `POST /api/query {"input": "handiwork:3"}` 英文工种也支持
- [ ] `POST /api/query {"input": "handiwork:3,mining:3"}` 多条件查询
- [x] `POST /api/query {"input": "手工"}`（缺省等级）默认 level=1

### 9.3 边界

- [x] `POST /api/query {"input": "手工:100"}` 返回空 + `max_available` + fallback
- [ ] `POST /api/query {"input": "打铁:5"}` 返回工种不合法提示

### 9.4 性能

- [x] `/health` 返回 `pals_loaded ≥ 0`
- [x] 单次查询响应 < 500ms
- [x] Swagger UI `/docs` 可用
