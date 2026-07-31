# 数据层需求文档

> 版本: v1.1 | 日期: 2026-07-31 | 状态: 设计完成

---

## 目录

1. [概述与目标](#1-概述与目标)
2. [数据源分析](#2-数据源分析)
3. [数据模型详细规格](#3-数据模型详细规格)
4. [数据采集流水线](#4-数据采集流水线)
5. [数据质量要求](#5-数据质量要求)
6. [中文语义映射设计](#6-中文语义映射设计)
7. [配种规则数据](#7-配种规则数据)
8. [数据版本管理](#8-数据版本管理)
9. [边界与特殊情况](#9-边界与特殊情况)
10. [验收标准](#10-验收标准)
11. [接口契约 — 适配器层](#11-接口契约--适配器层)
12. [PostgreSQL 存储方案](#12-postgresql-存储方案)

---

## 1. 概述与目标

### 1.1 数据层的定位

数据层是整个 Agent 的**基石**。所有配种计算、属性查询、NLU 解析都依赖这层数据。数据不准，一切白费。

### 1.2 核心目标

| 目标 | 度量标准 |
|------|---------|
| 数据完整 | 覆盖全部 204+ 帕鲁，关键字段完整率 ≥ 99% |
| 数据准确 | CombiRank 与游戏实际值一致，工作适应性等级正确 |
| 数据可维护 | 游戏更新后 2 天内可产出新版本数据 |
| 中文可用 | 帕鲁中文名、工种中文名、别称完整覆盖 |
| 可追溯 | 每次数据更新有 changelog，历史版本可回滚 |

### 1.3 数据范围

```
必须采集:
  ✅ 全部帕鲁基础信息 (名称/编号/属性/稀有度)
  ✅ CombiRank 繁殖力值
  ✅ 工作适应性 (12种类型 + 等级)
  ✅ 野外捕获标记 (is_wild)

辅助采集:
  ✅ 图片 URL
  ✅ Wiki 链接
  ✅ 帕鲁别名 (别称/昵称)

手工维护:
  ⚙️ 特殊配种规则 (约 40 条)
  ⚙️ 中文语义映射 (工种别名/口语化表达)
  ⚙️ 不可配种帕鲁列表
```

---

## 2. 数据源分析

### 2.1 主数据源：paldb.cc

| 属性 | 详情 |
|------|------|
| URL | `https://paldb.cc/cn/{PalName}` |
| 渲染方式 | 服务端渲染 HTML（非 SPA），可直接解析 |
| 数据来源 | 游戏解包数据（DT_ 系列 DataTable） |
| 当前版本 | v1.0.2 (2026-07-29) |
| 语言 | 中文界面，帕鲁名/工种均为中文 |
| 更新频率 | 跟随游戏版本更新 |

### 2.2 帕鲁页面 HTML 结构分析

以阿努比斯页面 (`paldb.cc/cn/Anubis`) 为例：

#### 页面标题区域
```html
<!-- 提取: cn_name="阿努比斯", number=139 -->
TAnubisiconnormal 阿努比斯 #139
```

#### CombiRank
```
CombiRank 480
正则: CombiRank\s+(\d+)
```

#### 工作适应性
```
[手工作业](...) Lv6  [采矿](...) Lv6  [搬运](...) Lv4
提取方式: 遍历 12 种工种关键词, 匹配 "Lv{数字}"
```

#### 属性
```
ElementType1 Earth
正则: ElementType1\s+(\w+)
也有 ElementType2 (双属性帕鲁)
```

#### 稀有度
```
Rarity 10
正则: Rarity\s+(\d+)
```

#### 野外生成 (Spawner)
```
Spawner 区域:
  TAnubisiconnormal 阿努比斯 | Lv. 68–72 | desertisland_1 (Wild)
判断: 存在 "(Wild)" 标记 → is_wild = true
```

#### 图片
```
cdn.paldb.cc/image/Pal/Texture/PalIcon/Normal/T_Anubis_icon_normal.webp
正则: (https?://cdn\.paldb\.cc/image[^"'\s]+\.(?:webp|png))
```

#### 配种相关链接
```
[Parent Calculator](https://paldb.cc/cn/Breed?child=Anubis)
[Breed 2 Pals](https://paldb.cc/cn/Breed?parent2a=Anubis)
```

#### 广告重定向处理

paldb.cc 使用广告平台 (inmobi / nitropay)，部分页面请求可能重定向到广告域。
爬虫策略:
- 使用 `follow_redirects=True` 跟随重定向
- 判断最终 URL host 是否仍为 `paldb.cc`，若非则丢弃该响应
- 广告重定向不计入重试次数，自动重试

### 2.3 帕鲁列表获取

所有帕鲁的 URL 名称可从配种页面提取：

```
URL: https://paldb.cc/cn/Breed?child=Anubis
提取区域: "Multi-pal Breeder" 部分
包含全部 204 个帕鲁的图片和链接
每个图片的 alt 或链接包含内部 ID (如 T_SheepBall_icon_normal → SheepBall → Lamball)
```

**注意**: paldb.cc 的 URL 使用的是帕鲁的内部英文名（非图鉴英文名），需要建立映射关系。

**ID 映射建立步骤**:
```
1. 从 Multi-pal Breeder 的图片文件名提取 internal_id
   例: T_SheepBall_icon_normal → internal_id = "SheepBall"
2. 从页面标题提取 cn_name 和 number
   例: "棉悠悠 #001" → cn_name="棉悠悠", number=1
3. 访问 /cn/{internal_id} 确认可正常访问
4. 从该帕鲁页面提取真正的 en_name (Code 字段)
   例: Code: Lamball → en_name="Lamball"
5. 建立映射: internal_id(SheepBall) → en_name(Lamball)
6. 后续使用 pal_id = en_name 作为主键
```

### 2.4 备选数据源

| 数据源 | 用途 | 优先级 |
|--------|------|:---:|
| 游戏 DataTable (FModel 导出) | CombiRank 交叉校验 | 2 |
| [palworld.wiki.gg](https://palworld.wiki.gg) | 补充别称/描述 | 3 |
| 社区 Google Sheets | 特殊配种规则参考 | 3 |

---

## 3. 数据模型详细规格

### 3.1 `pal_data.json` — 帕鲁核心数据

```jsonc
// 顶层: 以 pal_id (英文内部名) 为 key 的字典
{
  "Anubis": {
    // ===== 标识 =====
    "id": "Anubis",                // string, 唯一标识, 内部英文名, 必填
    "number": 139,                 // int, 图鉴编号, 必填, 1-204+
    "cn_name": "阿努比斯",          // string, 中文名, 必填
    "en_name": "Anubis",           // string, 英文名, 必填 (可能与 id 不同)
    "aliases": ["狗头", "埃及狗"],  // string[], 别称列表, 可空

    // ===== 配种核心 =====
    "combi_rank": 480,             // int, CombiRank 繁殖力值, 必填, 1-9999

    // ===== 属性 =====
    "elements": ["Earth"],         // string[], 属性列表, 必填
                                   // 可选: Fire/Water/Grass/Earth/Electric/Ice/Dragon/Dark/Neutral
    "rarity": 10,                  // int, 稀有度, 必填, 1-20

    // ===== 工作适应性 =====
    // 只存储非零值, 读取时缺失字段视为 0. 等级范围 0-10.
    "work_suitability": {
      "handiwork": 6,
      "mining": 6,
      "transporting": 4
    },

    // ===== 获取方式 =====
    "is_wild": true,               // bool, 是否野外可捕获, 必填
    "spawn_locations": [           // string[], 主要出没区域, 可选
      "desertisland_1"
    ],

    // ===== 展示 =====
    "image_url": "https://cdn.paldb.cc/image/...webp",  // string, 可选
    "wiki_url": "https://palworld.fandom.com/wiki/Anubis" // string, 可选
  }
}
```

#### 字段约束

| 字段 | 类型 | 必填 | 范围/格式 | 说明 |
|------|------|:---:|----------|------|
| `id` | string | ✅ | `[A-Z][a-zA-Z0-9_]*` | 内部唯一标识 |
| `number` | int | ✅ | 1 - 999 | 图鉴编号, 唯一 |
| `cn_name` | string | ✅ | 非空 | 中文名, 官方译名 |
| `en_name` | string | ✅ | 非空 | 英文名, 官方名称 |
| `aliases` | string[] | ❌ | 每项长度 ≥ 1 | 别称/昵称 |
| `combi_rank` | int | ✅ | 1 - 9999 | 繁殖力值, 唯一性不保证 |
| `elements` | string[] | ✅ | 长度 1-2 | 从枚举值中选择 |
| `rarity` | int | ✅ | 1 - 10 | 稀有度 |
| `work_suitability[*]` | int | ❌ | 0 - 10 | 等级, 不设硬上限 (实际值优先) |
| `is_wild` | bool | ✅ | true/false | 野外可捕获标记 |
| `image_url` | string | ❌ | 合法 URL | 帕鲁图片 |
| `wiki_url` | string | ❌ | 合法 URL | Wiki 页面 |

### 3.2 `breeding_rules.json` — 配种规则

```jsonc
{
  // 游戏版本
  "game_version": "v1.0.2",
  "last_updated": "2026-07-31",

  // 特殊组合: 固定父母 → 固定子代
  // 这些规则优先于 CombiRank 计算
  "special_combinations": [
    {
      "parent_a": "Relaxaurus",      // 父代 A 的 pal_id
      "parent_b": "Sparkit",         // 父代 B 的 pal_id (顺序无关)
      "child": "Relaxaurus Lux",     // 子代 pal_id
      "note": "雷棘龙 + 电棘鼠 = 雷棘龙·勒克斯"
    }
    // ... 约 35 条
  ],

  // 仅能同类繁殖 (传说帕鲁)
  "self_only": [
    {
      "pal_id": "Frostallion",
      "note": "唤冬兽只能由唤冬兽+唤冬兽繁殖"
    },
    {
      "pal_id": "Jetragon",
      "note": "空涡龙只能由空涡龙+空涡龙繁殖"
    }
    // Paladius, Necromus, Jormuntide Ignis ...
  ],

  // 不可通过配种获得 (Boss/塔主专属)
  "unbreedable": [
    {
      "pal_id": "TowerBoss_Grizzbolt",
      "note": "塔主暴电熊, 不可配种"
    }
    // 需要确认具体列表
  ],

  // 配种排除 (某些帕鲁不参与普通配种计算, 但不属于以上分类)
  "breeding_excluded": [
    // 非标准帕鲁, 如特殊 NPC 帕鲁
  ],

  // 突变组合 (1.0 新机制, 特定组合产生特殊后代)
  "mutations": [
    {
      "parent_a": "XXX",           // 父代 A
      "parent_b": "YYY",           // 父代 B
      "child": "ZZZ",              // 突变子代
      "note": ""
    }
    // 需要确认具体列表
  ]
}
```

#### 特殊组合规则发现方法

1. **从 paldb.cc Breed 页面验证**: 如果 `Breed?child=XXX` 返回的父代对与 CombiRank 计算结果不一致，则为特殊组合
2. **参考社区数据**: 已知的特殊组合约 35 条（亚种帕鲁的获取方式）
3. **交叉验证**: 用 paldb.cc 的 "Parent Calculator" 与自算结果对比

---

## 4. 数据采集流水线

### 4.1 整体流程

```
┌─────────────────────────────────────────────────────────┐
│                   数据采集流水线 (离线)                     │
│                                                         │
│  Step 1          Step 2          Step 3       Step 4    │
│  ┌────────┐     ┌────────┐     ┌────────┐   ┌────────┐ │
│  │ 获取    │────▶│ 抓取    │────▶│ 解析    │──▶│ 校验    │ │
│  │ Pal 列表│     │ 页面    │     │ 数据    │   │ 输出    │ │
│  └────────┘     └────────┘     └────────┘   └────────┘ │
│      │              │              │             │       │
│      ▼              ▼              ▼             ▼       │
│  paldb.cc       raw HTML      结构化数据     pal_data   │
│  /Breed 页面    pages/        extracted/     .json      │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Step 1: 获取帕鲁列表

```
输入: 无 (或 paldb.cc 基准 URL)
动作:
  1. GET https://paldb.cc/cn/Breed?child=Lamball
  2. 解析 "Multi-pal Breeder" 区域
  3. 提取所有帕鲁的内部 ID 和中文名
  4. 建立 internal_id → cn_name 映射表
输出:
  pal_list.json:
  [
    {"internal_id": "SheepBall", "cn_name": "棉悠悠", "number": 1},
    {"internal_id": "PinkCat",  "cn_name": "捣蛋猫", "number": 2},
    ...
  ]
注意: internal_id 可能与图鉴英文名不同,需验证
```

### 4.3 Step 2: 批量抓取页面

```
输入: pal_list.json
动作:
  对每个帕鲁:
    1. GET https://paldb.cc/cn/{internal_id}
    2. 保存原始 HTML 到 data/raw/pages/{internal_id}.html
    3. 请求间隔 ≥ 1 秒 (礼貌爬取)
    4. 失败重试 3 次, 指数退避 (1s → 2s → 4s)
    5. 3 次全失败 → 标记 failed, 记录到 fetch_errors.log, 继续下一个
输出:
  data/raw/pages/SheepBall.html
  data/raw/pages/PinkCat.html
  ...
  fetch_errors.log (如有)
```

**爬取策略**:
- 并发数: 3-5 (不要给站点压力)
- 间隔: 1-2 秒
- 超时: 30 秒
- User-Agent: `PlAgent/1.0 (pal-breeding-agent; contact@example.com)`
- 遵循 robots.txt

### 4.4 Step 3: 解析 HTML → 结构化数据

```
输入: data/raw/pages/{internal_id}.html
动作:
  对每个 HTML 文件:
    1. 用 BeautifulSoup 解析
    2. 提取各字段 (见 §2.2 字段映射)
    3. 组装为 Pal 实体
    4. 写入 data/raw/extracted/{pal_id}.json
输出:
  data/raw/extracted/Anubis.json:
  {
    "id": "Anubis",
    "number": 139,
    "cn_name": "阿努比斯",
    ...
    "_parse_warnings": []  // 解析异常记录
  }
```

**字段提取优先级**:
```
P0 (必须成功): id, number, cn_name, combi_rank, elements, is_wild
P1 (尽量成功): en_name, rarity, work_suitability
P2 (可选):     image_url, wiki_url, aliases, spawn_locations

解析失败处理:
  - P0 字段解析失败 → 标记 _incomplete=true, 记录 error
  - P1/P2 字段解析失败 → 字段置 null/空, 记录 warning
  - 某字段值异常 → 保留原始值, 标记 _suspicious=true
```

### 4.5 Step 4: 校验与输出

```
输入: data/raw/extracted/*.json
动作:
  1. 字段完整性检查
  2. CombiRank 唯一性/合理性检查
  3. 工作适应性逻辑检查 (等级范围、工种名称)
  4. is_wild 标记合理性
  5. 生成 data/processed/pal_data.json
  6. 生成校验报告 validation_report.md
输出:
  data/processed/pal_data.json     ← 正式数据
  data/processed/validation_report.md ← 校验报告
```

---

## 5. 数据质量要求

### 5.1 自动校验规则

| 编号 | 规则 | 类型 | 严重度 |
|:---:|------|------|:---:|
| V1 | `number` 唯一, 无重复/缺失 | 唯一性 | 🔴 Error |
| V2 | `id` 唯一, 无重复 | 唯一性 | 🔴 Error |
| V3 | `combi_rank` > 0 | 范围 | 🔴 Error |
| V4 | `cn_name` 非空且长度 ≥ 1 | 存在性 | 🔴 Error |
| V5 | `elements` 数组非空, 每项在枚举值内 | 枚举 | 🔴 Error |
| V6 | `rarity` 在 1-10 范围内 | 范围 | 🟡 Warn |
| V7 | `work_suitability` 等级 ≤ 10, 超出则 WARN | 范围 | 🟡 Warn |
| V8 | `is_wild=true` 的帕鲁数量 ≥ 全部帕鲁的 50% | 合理性 | 🟡 Warn |
| V9 | 所有 `is_wild=true` 的帕鲁 combi_rank 应在合理区间 | 合理性 | 🔵 Info |
| V10 | 相邻编号的帕鲁 combi_rank 无剧烈跳变 (>500) | 异常检测 | 🔵 Info |

### 5.2 人工抽查清单

- [ ] 抽查 5 个帕鲁的 CombiRank，与 paldb.cc 页面比对
- [ ] 抽查 3 个帕鲁的工作适应性，确认等级和工种正确
- [ ] 确认所有传说帕鲁标记为 `is_wild=true`（它们野外可捕获）
- [ ] 确认塔主/Boss 帕鲁标记为 `is_wild=false` 且在配种排除列表
- [ ] 验证特殊组合中的帕鲁 ID 在 `pal_data.json` 中存在

### 5.3 异常处理策略

| 异常场景 | 处理方式 |
|---------|---------|
| 某帕鲁页面抓取失败 | 记录到 error log，继续抓其他；全部完成后重试失败的 |
| 某字段解析失败 | 标记为 null，记录 warning，不阻塞其他字段 |
| CombiRank 解析为多个值 | 取第一个匹配值，记录 warning |
| 工作适应性等级超出 0-5 | 保留实际值，记录 warning（可能是新版改动） |
| 双属性帕鲁 ElementType2 解析失败 | 至少保留 ElementType1，记录 warning |
| paldb.cc 页面结构变更 | 爬虫脚本告警，需人工调整解析规则 |

---

## 6. 中文语义映射设计

### 6.1 `zh_mapping.json`

```jsonc
{
  // ===== 工作类型中文映射 =====
  // 用户可能用各种说法表达同一工种
  "work_types": {
    "handiwork":                ["手工", "手工作业", "制作", "手艺"],
    "kindling":                 ["生火", "烧火", "点火", "火焰", "火"],
    "watering":                 ["浇水", "灌溉", "洒水", "水"],
    "planting":                 ["播种", "种植", "种地", "农耕", "草"],
    "generating_electricity":   ["发电", "电力", "充电", "雷", "电"],
    "gathering":                ["采集", "收获", "收集"],
    "lumbering":                ["伐木", "砍树", "木材", "木"],
    "mining":                   ["采矿", "挖矿", "矿石", "矿"],
    "cooling":                  ["冷却", "降温", "制冷", "冰", "冻"],
    "medicine":                 ["制药", "医药", "药品", "治疗"],
    "transporting":             ["搬运", "运输", "运送", "搬"],
    "farming":                  ["牧场", "放牧", "畜牧", "养殖"]
  },

  // ===== 帕鲁别称 =====
  "pal_nicknames": {
    "Lamball":       ["棉悠悠", "棉棉", "悠悠", "棉花糖"],
    "Cattiva":       ["捣蛋猫", "猫", "粉猫"],
    "Anubis":        ["阿努比斯", "狗头", "埃及狗", "阿努"],
    "Frostallion":   ["唤冬兽", "冰马", "冰霜马"],
    "Jetragon":      ["空涡龙", "喷气龙", "飞机龙"],
    "Shadowbeak":    ["暗黑贝卡", "暗影鸟", "黑鸟"]
    // ... 需补全
  },

  // ===== 等级表达映射 =====
  "level_patterns": [
    "{等级}级",       // "10级"
    "lv{等级}",       // "lv10"
    "Lv{等级}",       // "Lv10"
    "{等级}",         // "10"
    "最高级",         // → level = "max"
    "最高",           // → level = "max"
    "顶级"            // → level = "max"
  ],

  // ===== 意图触发词 =====
  "intent_triggers": {
    "suitability_query": [
      "{工种}{等级}",          // "手工10级"
      "要{工种}的",            // "要手工的"
      "{工种}最高的",          // "采矿最高的"
      "会{工种}的帕鲁",        // "会手工的帕鲁"
      "既能{工种}又能{工种}"    // "既能手工又能搬运"
    ],
    "name_query": [
      "{帕鲁名}怎么配",
      "{帕鲁名}配种",
      "怎么合成{帕鲁名}",
      "需要{帕鲁名}"
    ]
  }
}
```

### 6.2 别称维护策略

- **初始别称**: 从社区 (贴吧/B站/NGA) 收集常用昵称，手工录入
- **持续补充**: 用户使用过程中发现未命中的搜索词，通过反馈机制补入
- **优先级**: 高频别称优先 > 冷门别称后补

---

## 7. 配种规则数据

### 7.1 规则分类

```
配种规则
├── normal (标准规则)
│   └── 基于 CombiRank 算法: child = nearest(round((a+b)/2))
│
├── special (特殊组合)
│   └── 约 35 条固定父母组合 (主要为亚种帕鲁)
│       例: Relaxaurus + Sparkit → Relaxaurus Lux
│
├── self_only (仅同类繁殖)
│   └── 传说帕鲁 + 部分特殊帕鲁
│       例: Frostallion / Jetragon / Paladius / Necromus
│
├── unbreedable (不可配种)
│   └── Boss/塔主专属帕鲁
│       例: 塔主暴电熊、塔主百合女王
│
└── mutation (突变/特殊后代)
    └── 特定组合产生稀有变异 (1.0 新机制, 需确认)
```

### 7.2 规则验证方法

对每条特殊组合规则，需执行：

```
1. 在 pal_data.json 中查找 parent_a、parent_b、child
2. 用 CombiRank 算法计算正常结果
3. 确认: 正常结果 ≠ 特殊组合结果 (否则不需要特殊规则)
4. 在 paldb.cc 上验证: /Breed?parent_a=XXX&parent_b=YYY
5. 确认 paldb.cc 返回结果与规则一致
```

---

## 8. 数据版本管理

### 8.1 版本号规则

```
格式: v{游戏大版本}.{数据迭代号}
示例: v1.0.2-1 → 基于游戏 v1.0.2 的第 1 版数据
      v1.0.2-2 → 修复了第 1 版中的错误
      v1.1.0-1 → 游戏更新到 v1.1.0 后的首版数据
```

### 8.2 文件组织

```
data/
├── processed/
│   └── pal_data.json              ← 当前最新数据 (软链接或直接使用)
│
├── archive/
│   ├── v1.0.2-1/
│   │   ├── pal_data.json
│   │   ├── breeding_rules.json
│   │   └── CHANGELOG.md
│   ├── v1.0.2-2/
│   │   └── ...
│   └── v1.1.0-1/
│       └── ...
│
└── raw/
    ├── pages/                      ← 爬虫原始 HTML
    └── extracted/                  ← 解析后的中间数据
```

### 8.3 Changelog 格式

```markdown
## v1.0.2-1 (2026-07-31)

### 新增
- 初始数据爬取完成, 覆盖 204 个帕鲁

### 修改
- (无)

### 修复
- (无)

### 数据统计
- 总帕鲁数: 204
- 野外可捕获: 156
- 特殊配种规则: 35 条
- 字段完整率: 98.5%
```

---

## 9. 边界与特殊情况

### 9.1 帕鲁分类特殊处理

| 分类 | 帕鲁示例 | 特殊处理 |
|------|---------|---------|
| 传说帕鲁 | Frostallion, Jetragon | self_only 繁殖规则 |
| 亚种帕鲁 | Relaxaurus Lux, Incineram Noct | 固定父母组合 |
| Boss 帕鲁 | 塔主系列 | 标记为不可配种 |
| 屋久岛变体 | YakushimaMonster001 (多色) | 共用一个 number? 需确认 |
| NPC 帕鲁 | 商人、守卫 | 排除出配种计算 |
| 1.0 新增帕鲁 | Bastigor, Dandilord, Xenolord | 数据可能不完整, 需重点校验 |

### 9.2 CombiRank 边界情况

```
最小 CombiRank: 传说帕鲁 (10-50 区间)
最大 CombiRank: 常见低级帕鲁 (1000+)

配种计算注意:
  - 子代 CombiRank = round((a+b)/2)
  - 寻找最接近的 CombiRank 值, 不能精确匹配时取最近的
  - 如果两个帕鲁 CombiRank 差值相等, 按图鉴编号优先取小的
```

### 9.3 工作适应性特殊情况

- **帕鲁无任何工作适应性**: 仅战斗帕鲁, 如部分传说帕鲁
- **浓缩提升等级**: 游戏内通过浓缩可以提升工作适应性等级，但配种计算使用**基础值**
- **新版本等级上限**: 1.0 版本可能增加工作等级上限 (原为 5 级, 可能增至 6 或更高)

### 9.4 数据缺失处理

| 场景 | 处理 |
|------|------|
| 新增帕鲁数据缺失 | 标记 `_incomplete: true`，记录缺失字段列表 |
| 某字段值异常 | 标记 `_suspicious: true` + `_suspicious_fields: [...]` |
| 配种规则未验证 | 标记 `_verified: false`，优先人工核实 |

---

## 10. 验收标准

### 10.1 Phase 1 验收标准 (数据爬取)

- [ ] `pal_list.json` 包含 200+ 帕鲁
- [ ] 每个帕鲁的 HTML 页面成功抓取 (成功率 ≥ 95%)
- [ ] 解析成功率 ≥ 98%
- [ ] 所有 V1-V5 必填字段完整率 ≥ 99%
- [ ] 输出 `data/processed/pal_data.json`

### 10.2 Phase 2 验收标准 (数据质量)

- [ ] 随机抽查 10 个帕鲁，CombiRank 与 paldb.cc 一致
- [ ] 随机抽查 5 个帕鲁，工作适应性与 paldb.cc 一致
- [ ] `is_wild` 标记抽查 10 个，逻辑正确
- [ ] `breeding_rules.json` 包含 ≥ 30 条特殊组合
- [ ] 所有 self_only 帕鲁正确标记

### 10.3 Phase 3 验收标准 (可维护性)

- [ ] 重现运行爬虫脚本，核心字段 (combi_rank, work_suitability) 结果一致
- [ ] 修改单条数据后重新生成，其他数据不受影响
- [ ] 通过配置文件切换数据版本
- [ ] 有 chanelog 记录每次数据变更

---

## 附录 A: 工具依赖

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | ≥ 3.10 | 爬虫 & 数据处理 |
| httpx | ≥ 0.25 | 异步 HTTP 客户端 |
| BeautifulSoup4 | ≥ 4.12 | HTML 解析 |
| 无需数据库 | — | JSON 文件足够 |

## 附录 B: paldb.cc 完整工种关键词对照表

| 中文 (paldb.cc) | 英文 (内部字段) | 游戏内显示 |
|----------------|----------------|-----------|
| 手工作业 | handiwork | 手工 |
| 生火 | kindling | 生火 |
| 浇水 | watering | 浇水 |
| 播种 | planting | 播种 |
| 发电 | generating_electricity | 发电 |
| 采集 | gathering | 采集 |
| 伐木 | lumbering | 伐木 |
| 采矿 | mining | 采矿 |
| 冷却 | cooling | 冷却 |
| 制药 | medicine | 制药 |
| 搬运 | transporting | 搬运 |
| 牧场 | farming | 牧场 |

---

## 11. Adapter 架构 — 外部数据对接规范

### 11.1 设计原则

```
外部数据源 (paldb.cc / 游戏文件) ──▶ Adapter ──▶ canonical Schema ──▶ Core Engine
                                        │
                                  转换 + 校验层
                                  不污染核心逻辑
```

- **Core 引擎只认识 `schema.Pal`**，不直接依赖任何外部数据格式
- **所有数据源通过 Adapter 接入**，Adapter 负责将外部格式转换为 canonical Schema
- **新增数据源只需新增 Adapter**，Core 无需改动

### 11.2 目录结构

```
packages/adapters/
├── __init__.py
├── base.py               # Adapter 抽象接口 (PalDataSourceAdapter, BreedingRulesAdapter)
├── paldb/
│   ├── scraper.py        # HTTP 抓取 HTML
│   ├── parser.py         # HTML → 字段字典
│   └── adapter.py        # 字段字典 → schema.Pal
├── gamefile/
│   └── adapter.py        # FModel JSON → schema.Pal
└── validator.py          # 数据校验 (基于 schema 约束)
```

### 11.3 数据流

```
paldb.cc ─HTTP─▶ Scraper ─HTML─▶ Parser ─dict─▶ Adapter ─schema.Pal─▶ JSON file
                                                                         │
                                                                         ▼
                                                                   Core Engine
```

### 11.4 核心接口

```python
class PalDataSourceAdapter(ABC):
    """所有帕鲁数据源必须实现"""
    async def fetch_all(self) -> list[Pal]: ...
    source_name: str
    source_version: str
```

### 11.5 Schema 位置

**唯一 Schema 定义**: `packages/core/pl_agent/core/schema.py`

全项目所有模块通过以下方式引用:
```python
from pl_agent.core.schema import Pal, WorkSuitability, BreedingRules, Element, WorkType
```

---

## 12. PostgreSQL 存储方案

> 状态: 📝 方案已定，待实现 | 目标版本: v0.2

### 12.1 动机

当前数据以 JSON 文件 (`data/processed/pal_data.json`) 存储，适合原型阶段。但随着项目发展，有以下痛点：

| 痛点 | JSON 现状 | PostgreSQL 解决 |
|------|----------|----------------|
| 查询能力 | 只能在内存中遍历 | SQL 直接查，支持 WHERE / ORDER BY / JOIN |
| 并发写入 | 无锁，手动处理 | ACID 事务保证一致性 |
| 数据分析 | 需要写 Python 脚本 | SQL 聚合 / Grafana 直连 |
| 数据共享 | 拷贝 JSON 文件 | 多服务连接同一数据库 |
| 增量更新 | 全量替换文件 | UPSERT 按需更新单条记录 |
| 版本追溯 | 手动备份文件 | 时间戳 + 触发器自动记录 |

### 12.2 架构原则: 热缓存 + 冷查询

不是全量加载——而是让 PG 真正发挥作用：

1. **热缓存（内存）**: 配种引擎需要的 4 个核心字段 — `id`, `combi_rank`, `is_wild`, `work_suitability`(12 列)
   - BFS 反向搜索需要 O(n²) 次访问，必须 O(1) 内存查找
   - 启动时从 PG 一次性提取到 `BreedingIndex` (~10KB)
2. **冷查询（PG 直连）**: 展示/管理字段 — `image_url`, `wiki_url`, `spawn_locations`, `aliases`, 统计聚合
   - 单次请求，PG 直查更合理
   - 利用 SQL 能力：`WHERE handiwork >= 4 ORDER BY handiwork DESC`
3. **引擎接口不变** — `core` 包不依赖数据库驱动，热缓存通过轻量 `PalRef` dataclass 提供
4. **JSON 兼容降级** — PG 不可用时回退到 JSON 全量加载

### 12.3 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│  写入路径 (离线，一次性操作)                                       │
│                                                                   │
│  paldb.cc → scraper → parser → PalDBAdapter                      │
│                                    │                              │
│                                    ├─→ pal_data.json (保留兼容)   │
│                                    └─→ PostgresAdapter           │
│                                         │                        │
│                                         └─→ PostgreSQL           │
│                                              pals 表              │
│                                              breeding_rules 表    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  读取路径: 热缓存 (启动) + 冷查询 (运行时)                          │
│                                                                   │
│  启动时:                                                           │
│    PostgresLoader.load_hot()                                      │
│      SELECT id, combi_rank, is_wild, handiwork, ..., farming      │
│      FROM pals                                                    │
│      → BreedingIndex { by_id, by_rank, by_wild }  (~10KB)        │
│                                                                   │
│  运行时:                                                           │
│    配种引擎 ──▶ BreedingIndex (内存 O(1))                          │
│    API 详情 ──▶ PG: SELECT * FROM pals WHERE id = $1              │
│    统计面板 ──▶ PG: SELECT MAX(handiwork), AVG(...) FROM pals     │
│    候选筛选 ──▶ PG: SELECT id, cn_name FROM pals                  │
│                WHERE handiwork >= 4 ORDER BY handiwork DESC       │
│                                                                   │
│  PG 不可用时: DataLoader.load(pal_data.json) → 全量内存降级         │
└─────────────────────────────────────────────────────────────────┘
```

### 12.4 数据库 Schema

#### pals 表

```sql
CREATE TABLE pals (
    -- ▲ 热字段 (启动时提取到内存索引)
    id            TEXT PRIMARY KEY,              -- "Anubis"
    combi_rank    INTEGER NOT NULL,               -- 480
    is_wild       BOOLEAN NOT NULL DEFAULT FALSE, -- true
    handiwork               INTEGER NOT NULL DEFAULT 0,
    kindling                INTEGER NOT NULL DEFAULT 0,
    watering                INTEGER NOT NULL DEFAULT 0,
    planting                INTEGER NOT NULL DEFAULT 0,
    generating_electricity  INTEGER NOT NULL DEFAULT 0,
    gathering               INTEGER NOT NULL DEFAULT 0,
    lumbering               INTEGER NOT NULL DEFAULT 0,
    mining                  INTEGER NOT NULL DEFAULT 0,
    cooling                 INTEGER NOT NULL DEFAULT 0,
    medicine                INTEGER NOT NULL DEFAULT 0,
    transporting            INTEGER NOT NULL DEFAULT 0,
    farming                 INTEGER NOT NULL DEFAULT 0,

    -- ▼ 冷字段 (运行时按需从 PG 查询)
    number        INTEGER NOT NULL,               -- 139
    cn_name       TEXT NOT NULL,                  -- "阿努比斯"
    en_name       TEXT NOT NULL,                  -- "Anubis"
    elements      JSONB NOT NULL DEFAULT '[]',    -- ["Earth"]
    rarity        INTEGER NOT NULL DEFAULT 1,     -- 10
    aliases       JSONB NOT NULL DEFAULT '[]',
    image_url     TEXT,
    wiki_url      TEXT,
    spawn_locations JSONB NOT NULL DEFAULT '[]',
    medicine                INTEGER NOT NULL DEFAULT 0,
    transporting            INTEGER NOT NULL DEFAULT 0,
    farming                 INTEGER NOT NULL DEFAULT 0,

    -- 元数据
    aliases         JSONB NOT NULL DEFAULT '[]',
    image_url       TEXT,
    wiki_url        TEXT,
    spawn_locations JSONB NOT NULL DEFAULT '[]',
    data_source     TEXT NOT NULL DEFAULT 'paldb.cc',
    incomplete      BOOLEAN NOT NULL DEFAULT FALSE,

    -- 时间戳
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 核心索引
CREATE INDEX idx_pals_combi_rank ON pals(combi_rank);
CREATE INDEX idx_pals_is_wild ON pals(is_wild);
CREATE INDEX idx_pals_number ON pals(number);
CREATE INDEX idx_pals_cn_name ON pals(cn_name);

-- 工作适应性索引 (支持 WHERE handiwork >= 4)
CREATE INDEX idx_pals_handiwork ON pals(handiwork DESC);
CREATE INDEX idx_pals_mining ON pals(mining DESC);
```

#### breeding_rules 表

```sql
CREATE TABLE breeding_rules (
    id            SERIAL PRIMARY KEY,
    game_version  TEXT NOT NULL,
    rule_type     TEXT NOT NULL,     -- special_combination | self_only | unbreedable
    parent_a      TEXT,              -- (special_combination)
    parent_b      TEXT,
    child         TEXT,
    pal_id        TEXT,              -- (self_only / unbreedable)
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 12.5 设计决策: 工作适应性用 12 列而非 JSONB

| 方案 | 优点 | 缺点 |
|------|------|------|
| 12 独立列 | SQL 直接 `WHERE handiwork >= 4`；类型安全；可建索引 | 列多，ALTER TABLE 加字段 |
| 单个 JSONB | 灵活，与 Python dataclass 一致 | 查询需 `WHERE (ws->>'handiwork')::int >= 4`，啰嗦 | 

**决策**: 用 12 独立列。工种类别固定（12 种），不频繁变化。加载时映射回 `WorkSuitability` dataclass。

### 12.6 新增文件清单

```
data/sql/
├── 001_create_pals.sql          ← DDL 迁移脚本
└── 002_seed_data.sql            ← 种子数据 (可选)

packages/adapters/adapters/postgres/
├── __init__.py
├── config.py                    ← DB 连接配置 (DATABASE_URL)
├── adapter.py                   ← PostgresWriter: Pal → PG 批量写入
└── loader.py                    ← PostgresLoader: PG → list[Pal]
```

### 12.7 新增依赖

```toml
# packages/adapters/pyproject.toml
dependencies = [
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "pl-agent-core",
    "asyncpg>=0.30",       # ← 新增
]
```

### 12.8 实现步骤

| 步骤 | 内容 | 预计改动 |
|:---:|------|------|
| 1 | 创建 `data/sql/001_create_pals.sql` | DDL 迁移脚本 |
| 2 | 实现 `PostgresWriter` | 批量 UPSERT |
| 3 | 实现 `PostgresLoader` | 全量 SELECT → list[Pal] |
| 4 | 更新 `main.py` lifespan | PG 优先, JSON 降级 |
| 5 | 更新依赖配置 | `pyproject.toml` + `uv sync` |
| 6 | 测试 + 文档更新 | 确保 JSON 降级可用 |

### 12.9 验收标准

- [ ] `make scrape` 后数据同时写入 JSON 和 PostgreSQL
- [ ] API 启动时从 PG 加载数据 (< 500ms)
- [ ] PG 不可用时自动降级到 JSON 文件，服务正常启动
- [ ] `SELECT * FROM pals WHERE handiwork >= 4` 返回正确结果
- [ ] 所有 23 个已有测试仍然通过 (不依赖 PG)
