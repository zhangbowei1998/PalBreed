# 幻兽帕鲁配种 Agent — 架构设计文档

> 版本: v2.0 | 日期: 2026-08-04 | 状态: ARCHIVED — paldb.cc 时代的旧版全景架构，已被 design/ 与 agent/ 文档取代

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统全景架构](#2-系统全景架构)
3. [数据层 — 数据获取与维护](#3-数据层--数据获取与维护)
4. [核心引擎层 (已移除)](#4-核心引擎层-已移除)
5. [用户交互层](#5-用户交互层)
6. [技术栈选型](#6-技术栈选型)
7. [项目目录结构](#7-项目目录结构)
8. [关键数据流](#8-关键数据流)
9. [开发路线图](#9-开发路线图)
10. [风险与对策](#10-风险与对策)

---

## 1. 项目概述

### 1.1 项目定位

一个智能化的幻兽帕鲁配种助手 Agent，用户输入帕鲁名或"工种:等级"，系统通过 ORM 查询服务访问 PostgreSQL 计算 CombiRank 配种公式，返回所有可能的父母组合。

### 1.2 核心功能

| 编号 | 功能 | 描述 |
|------|------|------|
| F1 | **名称直查** | 输入帕鲁名 → 返回所有父母组合 |
| F2 | **属性反向查** | 输入"手工10级" → 列出候选帕鲁 → 用户选择 → 返回父母组合 |
| F3 | **语音输入** | 支持语音描述需求 (规划中) |
| F4 | **一级父母对** | 返回目标帕鲁的所有可配种父母组合，点击继续查询 |
| F5 | **统计面板** | 12 种工作适应性全帕鲁排名 |

### 1.3 非功能需求

- 配种查询通过 ORM 生成的 CROSS JOIN 一次性完成
- 单次查询响应时间 < 500ms
- 数据可更新（支持手动/半自动导入新版本数据）
- 支持中文自然语言输入

---

## 2. 系统全景架构

```
┌─────────────────────────────────────────────────────────────┐
│                      用 户 入 口                              │
│   ┌──────────┐  ┌──────────┐  ┌──────────────┐              │
│   │ 文本输入  │  │ 语音输入  │  │  Web UI      │              │
│   └────┬─────┘  └────┬─────┘  └──────┬───────┘              │
│        │             │               │                       │
├────────┼─────────────┼───────────────┼───────────────────────┤
│        ▼             ▼               ▼                       │
│   ┌──────────────────────────────────────┐                   │
│   │         NLU 意图解析层                │                   │
│   │  语音→文本 | 实体提取 | 意图分类       │                   │
│   └──────────────┬───────────────────────┘                   │
│                  │                                           │
│   ┌──────────────▼───────────────────────────────────────┐   │
│   │               FastAPI 应用层 (API)                     │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │   │
│   │  │ Parser   │  │ Routes   │  │ Formatter        │   │   │
│   │  │ 意图解析  │  │ ORM 配种  │  │ 响应格式化        │   │   │
│   │  │ 实体提取  │  │ 属性筛选  │  │ 文本/JSON        │   │   │
│   │  └──────────┘  └────┬─────┘  └──────────────────┘   │   │
│   │                     │                                 │   │
│   │              ┌──────┴──────────────┐                   │   │
│   │              │ SQLAlchemy Async ORM │                   │   │
│   │              └──────┬──────────────┘                   │   │
│   └─────────────────────┼─────────────────────────────────┘   │
│                         │                                    │
│   ┌─────────────────────▼─────────────────────────────────┐   │
│   │                   数据存储层                            │   │
│   │                                                        │   │
│   │  ┌──────────────────────────────────────────┐          │   │
│   │  │           PostgreSQL 16                   │          │   │
│   │  │  ┌──────────┐  ┌──────────────────────┐   │          │   │
│   │  │  │ pal 表    │  │ ORM 查询 (CROSS JOIN)│   │          │   │
│   │  │  └──────────┘  └──────────────────────┘   │          │   │
│   │  └──────────────────────────────────────────┘          │   │
│   └───────────────────────────────────────────────────────┘   │
│                                                                │
│   ┌───────────────────────────────────────────────────────┐   │
│   │              数据获取与维护通道 (离线)                    │   │
│   │  paldb.cc → scraper → parser → adapter → PostgreSQL    │   │
│   └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 数据层 — 数据获取与维护

### 3.1 数据模型定义

#### 3.1.1 核心帕鲁实体 `Pal`

```typescript
interface Pal {
  /** 唯一标识 (英文名, 如 "Anubis") */
  id: string;

  /** 图鉴编号 */
  number: number;

  /** 中文名 */
  cn_name: string;

  /** 英文名 */
  en_name: string;

  /** 别名列表 (昵称、简称等, 用于语音/模糊搜索) */
  aliases: string[];

  /** CombiRank — 繁殖力值 (配种计算核心参数) */
  combi_rank: number;

  /** 属性列表 (火/水/草/地/雷/冰/龙/暗/无) */
  elements: string[];

  /** 工作适应性 */
  work_suitability: {
    handiwork?: number;              // 手工作业
    kindling?: number;               // 生火
    watering?: number;               // 浇水
    planting?: number;               // 播种
    generating_electricity?: number; // 发电
    gathering?: number;              // 采集
    lumbering?: number;              // 伐木
    mining?: number;                 // 采矿
    cooling?: number;                // 冷却
    medicine?: number;               // 制药
    transporting?: number;           // 搬运
    farming?: number;                // 牧场
  };

  /** 是否为野外可捕获 (基础帕鲁的标志) */
  is_wild: boolean;

  /** 稀有度 (1-10, 影响配种中的特殊规则) */
  rarity: number;

  /** wiki 链接 (可选, 用于展示详细信息) */
  wiki_url?: string;

  /** 图片 URL (可选, 用于前端展示) */
  image_url?: string;
}
```

#### 3.1.2 配种规则 `BreedingRule`

```typescript
interface BreedingRule {
  /** 规则类型 */
  type: "normal" | "special" | "self_only" | "unbreedable";

  /**
   * normal:     基于 CombiRank 的标准配种
   * special:    固定父母组合 (如 Relaxaurus+Sparkit=Relaxaurus Lux)
   * self_only:  只能同类繁殖 (如 Frostallion+Frostallion=Frostallion)
   * unbreedable: 不可通过配种获得 (如部分 Boss 帕鲁)
   */

  /** 父代组合 → 子代 (仅 special/sel_only 类型使用) */
  parents_to_child?: Record<string, string[]>;

  /** 不可配种帕鲁列表 (仅 unbreedable 类型使用) */
  excluded_pals?: string[];
}
```

### 3.2 数据来源策略

```
数据优先级: paldb.cc 爬虫 > 游戏文件解包 > 手动补充
              (主力)        (备用校验)       (兜底)
```

#### 3.2.1 主数据源：paldb.cc HTML 爬虫

**目标字段映射**：

| 需要字段 | paldb.cc HTML 中的位置 | 提取方式 |
|---------|----------------------|---------|
| `cn_name` + `number` | 页面标题 `{中文名} #{编号}` | 正则匹配 |
| `combi_rank` | `CombiRank {数值}` | 正则匹配 |
| `work_suitability` | `{工种} Lv{等级}` | 正则匹配 + 字典映射 |
| `elements` | `ElementType1 {属性}` | 正则匹配 |
| `rarity` | `Rarity {数值}` | 正则匹配 |
| `is_wild` | Spawner 区域有 Wild 标记 | 判断是否存在野外生成 |
| `image_url` | `cdn.paldb.cc/image/...webp` | 正则匹配图片 URL |

**爬虫架构**：

```python
# scripts/build_data.py — 数据构建脚本

class PalDBScraper:
    """paldb.cc 数据爬取器"""

    BASE_URL = "https://paldb.cc/cn"

    async def get_all_pal_names(self) -> list[str]:
        """从 /Breed 页面 Multi-pal Breeder 区域提取所有帕鲁名称列表"""
        ...

    async def fetch_pal_page(self, pal_name: str) -> Pal:
        """抓取单个帕鲁页面并解析为 Pal 实体"""
        ...

    async def build_dataset(self) -> list[Pal]:
        """批量抓取并构建完整数据集"""
        ...
```

#### 3.2.2 备选数据源：游戏文件解包

```
游戏路径:
  Palworld/Content/Pal/DataTable/

关键文件:
  DT_PalCombiRank.uasset          → CombiRank 值
  DT_PalWorkSuitability.uasset    → 工作适应性
  DT_PalMonsterParameter.uasset   → 基础参数

工具: FModel / UE4SS
输出: JSON
```

#### 3.2.3 数据维护策略

```
           ┌──────────────┐
           │  paldb.cc     │
           │  (自动更新)    │
           └──────┬───────┘
                  │
           ┌──────▼───────┐     数据不一致时
           │  爬虫拉取     │──────────────┐
           └──────┬───────┘              │
                  │                      ▼
           ┌──────▼───────┐    ┌─────────────────┐
           │  diff 对比    │    │  手动补充/修正    │
           │  (与旧数据比较) │───▶│  manual_fix.json │
           └──────┬───────┘    └─────────────────┘
                  │
           ┌──────▼───────┐
           │  输出新版本    │
           │  pal_data.json │
           └──────────────┘
```

### 3.3 PostgreSQL 存储方案

#### 启动加载 + 运行时 SQL

```
┌─────────────────────────────────────────────────────────────┐
│                      PostgreSQL 16                          │
│   5 表: pal(288) + pal_element(375)                        │
│   + work_suitability(3456) + pal_aliase + breeding_rule    │
└────────────┬────────────────────────────┬───────────────────┘
             │                            │
    启动时全量加载                 运行时 SQL 查询
    (Parser 索引用)               (配种/属性/详情)
             │                            │
             ▼                            ▼
  ┌─────────────────┐          ┌────────────────────────┐
  │  API 内存 pals   │          │  ORM 查询服务           │
  │  (Parser 映射)   │          │                        │
  │                 │          │  配种 CROSS JOIN       │
  │  cn_name → Pal  │          │  属性 JOIN 筛选        │
  │                 │          │  详情/统计聚合          │
  └─────────────────┘          └────────────────────────┘
                                 每查询 ~10-50ms
```

> 配种计算完全由 PostgreSQL 完成，API 层通过 ORM 服务做参数绑定和结果解析。
> 属性筛选走参数化 JOIN (无 SQL 注入)，统计用 GROUP BY 替代 12 路 UNION ALL。

#### 兼容降级

PG 不可用时，自动回退到 JSON 全量加载 + Python 内存遍历。

---

## 4. 核心引擎层 (已移除)

> v0.2: 引擎层已删除。配种计算由 API 内 ORM 查询服务完成。核心包 (`core`) 仅保留数据模型 (`schema.py`) 和 JSON 降级加载 (`data_loader.py`)。

### 配种公式 (两步 SQL)

```sql
-- Step 0: 查特殊规则
SELECT br.rule_type, br.parent_a_id, br.parent_b_id
FROM breeding_rule br JOIN pal p ON br.child_id = p.id
WHERE p.game_id = $target_game_id;

-- Step 1: CombiRank 公式 (无特殊规则时)
SELECT a.cn_name AS parent_a, b.cn_name AS parent_b
FROM pal a, pal b
WHERE round((a.combi_rank + b.combi_rank) / 2.0) = $target_rank
  AND a.game_id != $target_game_id AND b.game_id != $target_game_id
  AND a.id <= b.id
```

两步流程: 先 breeding_rule 守卫 (unbreedable/same_species/fixed_pair)，再 CROSS JOIN。
返回一级父母组合，点击继续查询。无递归 BFS。

---

## 5. 用户交互层

### 5.1 NLU 意图解析

```
                    ┌─────────────┐
   用户输入 ────────▶│   意图分类    │
   "手工10级的帕鲁"   └──────┬──────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                  ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ 名称直查      │ │ 属性反向查    │ │ 模糊/语音     │
   │ "阿努比斯"    │ │ "手工10级"    │ │ "要个烧火的"  │
   │ intent:      │ │ intent:      │ │ intent:      │
   │  name_query  │ │  suit_query  │ │  fuzzy_query │
   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │                │                 │
          ▼                ▼                 ▼
   ┌──────────────────────────────────────────────────┐
   │              Parser 实体提取                       │
   │  name_query → SQL 配种 (CROSS JOIN)              │
   │  suit_query → SQL 属性筛选 (WHERE)               │
   └──────────────────────────────────────────────────┘
```

### 5.2 语音输入流程 (规划中)

```
用户语音 ──▶ ASR 语音识别 ──▶ 文本 ──▶ Parser 意图解析 ──▶ SQL 查询
```

### 5.3 输出格式

#### 父母对查询示例：

```
🎯 目标帕鲁: 墨罗娜
   手工作业 Lv8

🥚 父母组合 (22 对):
   1. 织夜鹿 + 燎火舞伶
   2. 霹雳犬 + 遁地鼠
   ...
```

---

## 6. 技术栈选型

| 层级 | 技术 | 理由 |
|------|------|------|
| **语言** | Python 3.10+ | 数据处理 + AI 生态成熟 |
| **数据存储** | PostgreSQL 16 (主) + JSON 降级 | ORM + CROSS JOIN 配种计算 |
| **数据爬虫** | httpx + BeautifulSoup4 | 异步 HTTP + HTML 解析 |
| **Web 框架** | FastAPI | 高性能 REST API，自动生成文档 |
| **前端 UI** | React / Vue 3 | 交互式配种结果展示 |
| **可视化** | N/A | 已简化为父母对列表 |
| **语音识别** | Web Speech API / Whisper | 浏览器端免费 / 本地高精度 |
| **NLU** | 规则引擎 + LLM (可选) | MVP 用正则规则，进阶接大模型 |
| **部署** | Docker | 一键部署，环境一致 |

### 6.1 为什么选择 Python？

- 数据爬取：`httpx` + `BeautifulSoup` 是最成熟的方案
- SQL 能力：`SQLAlchemy Async ORM` + `asyncpg` 驱动
- 已有参考代码：`PalWorldPlugin` 的配种算法就是 Python
- AI 集成：后续接 LLM 做自然语言理解，Python 生态最完善

---

## 7. 项目目录结构

```
pl-agent/
├── docs/                        # 📖 文档
│   ├── architecture/            #   架构与需求文档
│   ├── context/                 #   AI 接手上下文
│   └── decisions/               #   设计决策记录 (ADR)
│
├── packages/                    # 📦 monorepo 包
│   ├── core/                    # 📐 数据模型
│   │   └── pl_agent/core/
│   │       ├── schema.py        #   ★ canonical models
│   │       ├── errors.py        #   领域异常
│   │       ├── data_loader.py   #   JSON 降级加载
│   │       └── __tests__/
│   │
│   ├── adapters/                # 🔌 外部数据适配
│   │   └── adapters/
│   │       ├── base.py          #   Adapter 抽象借口
│   │       ├── validator.py     #   数据校验
│   │       ├── paldb/           #   paldb.cc 适配器
│   │       │   ├── scraper.py
│   │       │   ├── parser.py
│   │       │   ├── adapter.py
│   │       │   └── __tests__/
│   │       └── postgres/        #   PostgreSQL 适配器 (v0.2)
│   │           ├── adapter.py   #   Pal → PG 批量写入
│   │           └── loader.py    #   PG → list[Pal] 加载
│   │
│   ├── api/                     # 🌐 FastAPI 服务
│   │   └── pl_agent/api/
│   │       ├── main.py          #   入口 + lifespan
│   │       ├── parser.py        #   输入解析
│   │       ├── formatter.py     #   响应格式化
│   │       ├── routes/query.py  #   路由
│   │       └── __tests__/
│   │
│   ├── nlu/                     # 💬 意图解析 (v0.2)
│   └── web/                     # 🖥️ 前端 UI (v0.3)
│
├── data/                        # 📊 数据文件
│   ├── raw/                     #   爬虫原始 HTML
│   ├── processed/               #   构建产物 (JSON)
│   └── sql/                     #   PostgreSQL 迁移脚本
│
├── tests/                       # 🧪 测试
│   └── smoke/                   #   冒烟测试 (6 场景)
│
├── pyproject.toml               # uv workspace 配置
├── Makefile                     # 常用命令
└── README.md
```

---

## 8. 关键数据流

### 8.1 启动时数据加载

```
API 启动 (main.py lifespan):
  │
  ├── 1. 连接 PostgreSQL → 加载 pals 到内存 (Parser 索引用)
  │
  ├── 2. PG 不可用时降级
  │      DataLoader.load(pal_data.json) → 全量内存
  │
  └── 3. 创建 QueryParser (中文名 → Pal 映射)
```

### 8.2 用户查询"手工10级帕鲁"的完整流程

```
用户: "我要一个手工10级的帕鲁"
  │
  ▼
[Parser 意图解析]
  ├── 意图分类: suitability_query
  ├── 实体提取: work_type=handiwork, level=10
  └── 置信度: 0.95
  │
  ▼
[SQL 属性筛选]
  ├── SELECT cn_name, handiwork FROM pals
  │    WHERE handiwork >= 10
  │    ORDER BY handiwork DESC
  ├── 结果可能为空 → 返回"最高等级为X"提示
  └── 返回候选列表
  │
  ▼
用户选择: "阿努比斯"
  │
  ▼
[SQL 配种查询]
  ├── SELECT a.cn_name, b.cn_name
  │    FROM pals a, pals b
  │    WHERE round((a.combi_rank + b.combi_rank) / 2.0) = $rank
  │      AND a.id != $id AND b.id != $id AND a.id <= b.id
  └── 返回所有父母对 (一级)
  │
  ▼
[返回结果] → 用户看到父母组合列表，点击继续查询
```

### 8.3 数据更新流程

```
[检测到 paldb.cc 有新版本] 或 [游戏大更新后手动触发]
  │
  ▼
[运行 PalDBAdapter.build_and_save()]
  ├── 1. 爬取 paldb.cc 全部页面
  ├── 2. 解析 HTML → Pal
  ├── 3. 数据校验
  └── 4. 持久化 → PostgreSQL (UPSERT)
  │
  ▼
[重启 API 服务]
  → lifespan 重新加载 PostgreSQL → 内存
```

---

## 9. 开发路线图

### Phase 1: 数据基础 ✅

```
✅ 搭建项目骨架 (目录结构)
✅ 编写 paldb.cc 爬虫脚本
✅ 初次爬取全部帕鲁数据 (288 个)
✅ 手工整理特殊配种规则
✅ 校验数据完整性
✅ 生成 pal_data.json + PostgreSQL 导入
```

### Phase 2: API + PostgreSQL ✅

```
✅ FastAPI 服务 (routes/query.py)
✅ PostgreSQL 存储 + Docker Compose
✅ SQL CROSS JOIN 配种查询
✅ SQL 属性筛选
✅ Parser 意图解析
✅ 单元测试 (63 passed)
```

### Phase 3: 前端 UI (当前)

```
□ React/Vue 项目初始化
□ 搜索输入组件
□ 父母对列表组件
□ 逐层查询交互
```

### Phase 4: NLU 增强

```
□ LLM 增强 NLU (可选)
□ 语音识别集成
```

### Phase 5: 部署 + CI

```
□ Docker 容器化
□ CI/CD
□ 数据自动更新检测
```

---

---

## 10. 风险与对策

| 风险 | 等级 | 对策 |
|------|:---:|------|
| paldb.cc 改版导致爬虫失效 | 🔴 高 | 爬虫层独立封装，解析规则配置化；备选游戏文件解包方案 |
| 游戏更新后 CombiRank 大幅调整 | 🟡 中 | 数据版本化管理；diff 对比工具；保留历史版本 |
| 特殊配种规则遗漏 | 🟡 中 | 参考 paldb.cc 的 Breed Tree 结果交叉验证 |
| 中文语音识别准确率 | 🟡 中 | MVP 用文本输入；语音降级为辅助功能 |
| "手工10级"实际不存在 | 🟡 中 | 返回实际最高等级 + fallback |

---

> 📌 下一步: 前端 UI 开发 (`packages/web/`)
