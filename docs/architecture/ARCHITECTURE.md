# 幻兽帕鲁配种 Agent — 架构设计文档

> 版本: v1.0 | 日期: 2026-07-31

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统全景架构](#2-系统全景架构)
3. [数据层 — 数据获取与维护](#3-数据层--数据获取与维护)
4. [核心引擎层](#4-核心引擎层)
5. [用户交互层](#5-用户交互层)
6. [技术栈选型](#6-技术栈选型)
7. [项目目录结构](#7-项目目录结构)
8. [关键数据流](#8-关键数据流)
9. [开发路线图](#9-开发路线图)
10. [风险与对策](#10-风险与对策)

---

## 1. 项目概述

### 1.1 项目定位

一个智能化的幻兽帕鲁配种助手 Agent，用户通过**文字或语音**描述想要的目标帕鲁，系统返回**从基础帕鲁开始的完整配种树**。

### 1.2 核心功能

| 编号 | 功能 | 描述 |
|------|------|------|
| F1 | **名称直查** | 输入帕鲁名 → 返回配种树 |
| F2 | **属性反向查** | 输入"手工10级" → 列出候选帕鲁 → 用户选择 → 返回配种树 |
| F3 | **语音输入** | 支持语音描述需求 |
| F4 | **配种树输出** | 从野外可捕获的基础帕鲁开始，逐层展示配种路径 |
| F5 | **多路径择优** | 多条配种路径时，按步数最少 > 父代最易获得排序 |

### 1.3 非功能需求

- 配种树深度默认 ≤ 5 层
- 单次查询响应时间 < 2 秒
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
│   │  输入: "我要手工10级的帕鲁"            │                   │
│   │  输出: {intent:"suitability_query",   │                   │
│   │          work_type:"handiwork",       │                   │
│   │          level:10}                    │                   │
│   └──────────────┬───────────────────────┘                   │
│                  │                                           │
│   ┌──────────────▼───────────────────────────────────────┐   │
│   │                  核心引擎层                            │   │
│   │  ┌────────────┐ ┌──────────┐ ┌──────────────────┐   │   │
│   │  │ 属性查询器   │ │ 配种引擎  │ │ 配种树构建器      │   │   │
│   │  │ → 按工种查询 │ │ → 正向计算│ │ → BFS 反向搜索    │   │   │
│   │  │ → 等级筛选  │ │ → 反向查询│ │ → 递归展开        │   │   │
│   │  │ → 候选排序  │ │ → 特殊规则│ │ → 去重+择优       │   │   │
│   │  └─────┬──────┘ └────┬─────┘ └────────┬─────────┘   │   │
│   │        │             │               │               │   │
│   │        └─────────────┼───────────────┘               │   │
│   │                      │                               │   │
│   │         ┌────────────▼────────────┐                  │   │
│   │         │      数据访问层 (DAL)     │                  │   │
│   │         │  统一数据查询接口          │                  │   │
│   │         └────────────┬────────────┘                  │   │
│   └──────────────────────┼────────────────────────────────┘   │
│                          │                                    │
│   ┌──────────────────────▼────────────────────────────────┐   │
│   │                    数据存储层                           │   │
│   │  ┌──────────────────┐  ┌─────────────────────────┐    │   │
│   │  │   pal_data.json   │  │  breeding_rules.json    │    │   │
│   │  │   (帕鲁核心属性)    │  │  (特殊配种规则)          │    │   │
│   │  └──────────────────┘  └─────────────────────────┘    │   │
│   │  ┌──────────────────┐  ┌─────────────────────────┐    │   │
│   │  │  wild_pals.json   │  │  zh_mapping.json        │    │   │
│   │  │  (野外捕获列表)    │  │  (中文别名/昵称映射)     │    │   │
│   │  └──────────────────┘  └─────────────────────────┘    │   │
│   └───────────────────────────────────────────────────────┘   │
│                                                                 │
│   ┌───────────────────────────────────────────────────────┐   │
│   │              数据获取与维护通道 (离线)                    │   │
│   │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  │   │
│   │  │ paldb.cc     │  │ 游戏文件解包   │  │ 手动补充     │  │   │
│   │  │ HTML 爬虫     │  │ FModel 导出   │  │ 新帕鲁数据    │  │   │
│   │  └──────┬──────┘  └──────┬───────┘  └──────┬──────┘  │   │
│   │         │                │                  │          │   │
│   │         └────────────────┼──────────────────┘          │   │
│   │                          ▼                             │   │
│   │               ┌──────────────────┐                     │   │
│   │               │  数据构建脚本      │                     │   │
│   │               │  build_data.py    │                     │   │
│   │               └──────────────────┘                     │   │
│   └───────────────────────────────────────────────────────┘   │
│                          │                                    │
│                          ▼                                    │
│                   paldb.cc 网站                                │
│               (外部数据源, v1.0.2)                              │
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

### 3.3 数据文件规格

```
data/
├── pal_data.json          # 核心帕鲁数据 (手动/爬虫生成)
│   [{
│     "id": "Anubis",
│     "number": 139,
│     "cn_name": "阿努比斯",
│     "en_name": "Anubis",
│     "aliases": ["狗头", "埃及狗"],
│     "combi_rank": 480,
│     "elements": ["Earth"],
│     "work_suitability": {
│       "handiwork": 6,
│       "mining": 6,
│       "transporting": 4
│     },
│     "is_wild": true,
│     "rarity": 10,
│     "image_url": "https://cdn.paldb.cc/..."
│   }, ...]
│
├── breeding_rules.json    # 特殊配种规则
│   {
│     "special_combinations": [
│       {
│         "parent_a": "Relaxaurus",
│         "parent_b": "Sparkit",
│         "child": "Relaxaurus Lux"
│       }, ...
│     ],
│     "self_only": ["Frostallion", "Jetragon", "Paladius", "Necromus"],
│     "unbreedable": ["Boss_XXX", "Tower_YYY", ...]
│   }
│
├── wild_pals.json         # 基础帕鲁 (野外可捕获)
│   ["Lamball", "Cattiva", "Chikipi", ...]
│
└── zh_mapping.json        # 中文语义映射 (别名/口语化表达)
│   {
│     "work_types": {
│       "手工": "handiwork", "手工作业": "handiwork",
│       "烧火": "kindling", "生火": "kindling", "点火": "kindling",
│       "浇水": "watering", "灌溉": "watering",
│       ...
│     },
│     "pal_nicknames": {
│       "棉悠悠": ["棉棉", "悠悠"],
│       "阿努比斯": ["狗头", "埃及狗", "阿努"],
│       ...
│     }
│   }
```

---

## 4. 核心引擎层

### 4.1 模块总览

```
core/
├── suitability_query.py   # 属性反向查询器
├── breeding_engine.py     # 配种计算引擎
├── breeding_tree.py       # 配种树构建器
└── path_optimizer.py      # 配种路径择优器
```

### 4.2 属性反向查询器 (`suitability_query.py`)

```
输入: {work_type: "handiwork", min_level: 10}
  ↓
1. 遍历 pal_data.json 中所有 Pal
2. 筛选 work_suitability[handiwork] >= 10
3. 按等级降序排列
4. 返回候选列表

输出: [
  {pal: Pal, match_level: 10, match_type: "handiwork"},
  ...
]
```

**中文语义映射**（通过 `zh_mapping.json`）：

```
"手工10级"     → {work_type: "handiwork", level: 10}
"生火5级"      → {work_type: "kindling", level: 5}
"采矿最高的"    → {work_type: "mining", level: "max"}
"既能手工又能搬运" → [{work_type: "handiwork"}, {work_type: "transporting"}]
```

### 4.3 配种计算引擎 (`breeding_engine.py`)

#### 4.3.1 正向计算：父母 → 子代

```
function forward_breed(parent_a: Pal, parent_b: Pal) -> Pal:
    1. 查 special_combinations 特殊规则表
       if 命中 → 直接返回固定子代
    2. 查 self_only 表
       if 父母相同且是传说 → 返回自身
    3. 标准计算:
       child_rank = round((parent_a.combi_rank + parent_b.combi_rank) / 2)
       child = 按 CombiRank 排序后最接近 child_rank 的 Pal
    4. return child
```

#### 4.3.2 反向计算：子代 → 所有可能父母对

```
function reverse_breed(child: Pal) -> list[(Pal, Pal)]:
    1. 查特殊规则表
       if child 在 special_combinations 中 → 返回固定父母对
    2. 查 self_only 表
       if child 是传说 → 返回 [(child, child)]
    3. 查 unbreedable 表
       if child 不可配种 → 返回空
    4. 标准反向计算:
       - 找到 CombiRank 刚好在 child 前后的两个 Pal (prev, next)
       - 确定父母 CombiRank 总和区间
       - 枚举所有 CombiRank 组合满足区间的父母对
       - 返回列表 (可能有很多对)
```

### 4.4 配种树构建器 (`breeding_tree.py`)

```
function build_breeding_tree(target: Pal, max_depth: int = 5) -> BreedingTree:

    定义基础帕鲁: is_wild == true 的 Pal (野外可直接捕获)

    算法: BFS + 递归展开

    tree = {
        target: {
            父母对1: {
                父: { ...递归... },
                母: { ...递归... }
            },
            父母对2: { ... },
            ...
        }
    }

    终止条件:
      1. 当前 Pal 是基础帕鲁 (is_wild == true)
      2. 已达到最大深度 max_depth
      3. 当前 Pal 不可配种 (在 unbreedable 列表中)
      4. 检测到循环依赖 (visited 集合)

    去重:
      - 同一 Pal 在树中出现多次 → 保留深度最浅的路径
      - 合并重复子树
```

#### 配种树数据结构：

```
BreedingTree:
  ├── target: Pal           # 目标帕鲁
  ├── paths: BreedingPath[] # 所有可能的配种路径
  └── best_path: BreedingPath # 最优路径

BreedingPath:
  ├── steps: BreedingStep[] # 配种步骤列表 (从基础帕鲁开始)
  ├── total_steps: number   # 总步骤数
  ├── difficulty: number    # 难度评分 (越低越好)
  └── leaf_pals: Pal[]      # 需要从野外捕获的基础帕鲁列表

BreedingStep:
  ├── parent_a: Pal | BreedingPath  # 父代或子树
  ├── parent_b: Pal | BreedingPath  # 母代或子树
  ├── child: Pal                     # 产出子代
  └── method: "wild" | "breed"      # 获取方式
```

### 4.5 路径择优器 (`path_optimizer.py`)

排序策略（优先级从高到低）：

```
1. 步数最少 (total_steps 升序)
2. 基础帕鲁总数最少 (leaf_pals 数量升序)
3. 基础帕鲁平均稀有度最低 (越常见越好)
4. 不含传说/Boss帕鲁优先
```

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
   │              实体提取 + 消歧                        │
   │  提取: pal_name / work_type / level              │
   │  消歧: 候选列表 → 用户选择 OR 自动推荐最优           │
   └──────────────────────┬───────────────────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  核心引擎调用  │
                   └──────────────┘
```

### 5.2 语音输入流程

```
用户语音 ──▶ ASR 语音识别 ──▶ 文本 ──▶ NLU 意图解析 ──▶ 核心引擎
              │
              ├── Web Speech API (浏览器端, MVP)
              ├── Whisper 本地模型 (进阶)
              └── 讯飞/阿里云 ASR (生产环境)
```

### 5.3 输出格式

#### 文本输出示例：

```
🎯 目标帕鲁: 阿努比斯 (#139)
   工作适应性: 手工作业 Lv6 | 采矿 Lv6 | 搬运 Lv4

📋 最优配种路径 (2步):

   🌿 第一步: 野外捕获
      棉悠悠 + 捣蛋猫 = 疾旋鼬

   🥚 第二步: 配种
      疾旋鼬 + 烽歌龙 = 🎯 阿努比斯

   📝 备选方案:
   方案2: 棉悠悠 + 夜幕魔蝠 → 霹雳犬 → 霹雳犬 + 烽歌龙 → 阿努比斯 (3步)
   方案3: ...
```

#### 配种树可视化输出（进阶）：

```
         🌿棉悠悠(野生)  🌿捣蛋猫(野生)
              │              │
              └──────┬───────┘
                     │
                  🥚疾旋鼬          🌿烽歌龙(野生)
                     │                │
                     └───────┬────────┘
                             │
                         🎯阿努比斯
```

---

## 6. 技术栈选型

| 层级 | 技术 | 理由 |
|------|------|------|
| **语言** | Python 3.10+ | 数据处理 + AI 生态成熟 |
| **数据存储** | JSON 文件 → SQLite | 数据量 < 500 条，JSON 足够；后期可升级 SQLite |
| **数据爬虫** | httpx + BeautifulSoup4 | 异步 HTTP + HTML 解析 |
| **Web 框架** | FastAPI | 高性能 REST API，自动生成文档 |
| **前端 UI** | React / Vue 3 | 交互式配种树可视化 |
| **树形可视化** | D3.js / ECharts Tree | 配种树图形展示 |
| **语音识别** | Web Speech API / Whisper | 浏览器端免费 / 本地高精度 |
| **NLU** | 规则引擎 + LLM (可选) | MVP 用正则规则，进阶接大模型 |
| **部署** | Docker | 一键部署，环境一致 |

### 6.1 为什么选择 Python？

- 数据爬取：`httpx` + `BeautifulSoup` 是最成熟的方案
- 算法实现：配种树（图搜索）用 Python 写最灵活
- 已有参考代码：`PalWorldPlugin` 的配种算法就是 Python
- AI 集成：后续接 LLM 做自然语言理解，Python 生态最完善

---

## 7. 项目目录结构

```
pl-agent/
├── ARCHITECTURE.md              # 本架构文档
├── init.md                      # 初始需求
├── README.md                    # 项目说明
│
├── data/                        # 📦 数据文件 (静态)
│   ├── pal_data.json            #   帕鲁核心数据
│   ├── breeding_rules.json      #   特殊配种规则
│   ├── wild_pals.json           #   基础帕鲁列表
│   └── zh_mapping.json          #   中文语义映射
│
├── scripts/                     # 🔧 数据获取脚本 (离线运行)
│   ├── build_data.py            #   数据构建主脚本
│   ├── scraper_paldb.py         #   paldb.cc HTML 爬虫
│   ├── parser_html.py           #   HTML 解析器
│   ├── validator.py             #   数据校验器
│   └── diff_checker.py          #   新旧数据对比
│
├── core/                        # 🧠 核心引擎
│   ├── __init__.py
│   ├── models.py                #   数据模型 (Pal, BreedingRule 等)
│   ├── data_loader.py           #   数据加载器 (JSON → 内存)
│   ├── suitability_query.py     #   属性反向查询器
│   ├── breeding_engine.py       #   配种计算引擎
│   ├── breeding_tree.py         #   配种树构建器
│   └── path_optimizer.py        #   路径择优器
│
├── nlu/                         # 💬 自然语言理解
│   ├── __init__.py
│   ├── intent_classifier.py     #   意图分类 (规则 + LLM)
│   ├── entity_extractor.py      #   实体提取 (帕鲁名/工种/等级)
│   └── disambiguator.py         #   消歧处理
│
├── api/                         # 🌐 Web API 服务
│   ├── __init__.py
│   ├── main.py                  #   FastAPI 入口
│   ├── routes/
│   │   ├── breeding.py          #   /api/breeding 配种相关接口
│   │   └── query.py             #   /api/query 查询相关接口
│   └── schemas.py               #   API 请求/响应模型
│
├── web/                         # 🖥️ 前端 UI (可选)
│   ├── src/
│   │   ├── components/
│   │   │   ├── SearchBox.tsx    #   搜索输入框
│   │   │   ├── PalCard.tsx      #   帕鲁信息卡片
│   │   │   ├── BreedingTree.tsx #   配种树可视化
│   │   │   └── CandidateList.tsx#   候选帕鲁列表
│   │   └── App.tsx
│   └── package.json
│
├── tests/                       # 🧪 测试
│   ├── test_breeding_engine.py
│   ├── test_breeding_tree.py
│   ├── test_suitability.py
│   └── test_nlu.py
│
├── requirements.txt             # Python 依赖
├── Dockerfile                   # Docker 部署
└── docker-compose.yml           # 一键部署
```

---

## 8. 关键数据流

### 8.1 用户查询"手工10级帕鲁"的完整流程

```
时间线 →

用户: "我要一个手工10级的帕鲁"
  │
  ▼
[语音识别] (如果是语音)
  │
  ▼
[NLU 意图解析]
  ├── 意图分类: suitability_query
  ├── 实体提取: work_type=handiwork, level=10
  └── 置信度: 0.95
  │
  ▼
[属性反向查询器]
  ├── 查询 pal_data.json
  ├── 筛选 work_suitability.handiwork >= 10
  ├── 结果: [
  │     {pal: "阿努比斯", handiwork: 6},  ← 1.0版本最高手工就6级!
  │     {pal: "唤夜兽", handiwork: 5},
  │     ...
  │   ]
  └── 注: 如果等级超出实际范围, 返回"最高等级为X"的提示
  │
  ▼
[返回候选列表] → 用户看到:
  "手工≥10级的帕鲁不存在, 手工最高为Lv6。
   以下是手工Lv6的帕鲁:
   1. 阿努比斯 (手工6, 采矿6, 搬运4)
   2. ...
   请输入编号选择, 或输入帕鲁名"
  │
  ▼
用户选择: "1" 或 "阿努比斯"
  │
  ▼
[配种树构建器]
  ├── target = Anubis (combi_rank=480)
  ├── BFS 反向搜索
  ├── 递归展开到基础帕鲁
  ├── 去重 + 择优
  └── 生成 BreedingTree
  │
  ▼
[返回结果] → 用户看到配种树
```

### 8.2 数据更新流程

```
[检测到 paldb.cc 有新版本]
  或
[游戏大更新后手动触发]
  │
  ▼
[运行 scripts/build_data.py]
  ├── 1. 爬取 paldb.cc 所有帕鲁页面
  ├── 2. 解析 HTML → Pal 实体列表
  ├── 3. 对比旧数据 (diff_checker.py)
  │      ├── 新增帕鲁: +15 个
  │      ├── CombiRank 变化: 3 个
  │      └── 工作适应性变化: 5 个
  ├── 4. 校验数据完整性 (validator.py)
  └── 5. 输出新版本 pal_data.json
  │
  ▼
[更新 breeding_rules.json] (手动维护特殊规则)
  │
  ▼
[运行测试] → 确保配种计算正确
  │
  ▼
[部署新数据]
```

---

## 9. 开发路线图

### Phase 1: 数据基础 (Week 1)

```
□ 搭建项目骨架 (目录结构)
□ 编写 paldb.cc 爬虫脚本
□ 初次爬取全部帕鲁数据 (204 个)
□ 手工整理特殊配种规则
□ 校验数据完整性
□ 生成首批 pal_data.json + breeding_rules.json
```

### Phase 2: 核心引擎 (Week 2-3)

```
□ 实现数据加载器 (data_loader.py)
□ 实现属性反向查询器 (suitability_query.py)
□ 实现配种计算引擎 (breeding_engine.py)
   □ 正向计算 (父母→子代)
   □ 反向计算 (子代→父母对)
   □ 特殊规则处理
□ 实现配种树构建器 (breeding_tree.py)
   □ BFS 反向搜索
   □ 递归展开
   □ 去重
□ 实现路径择优器 (path_optimizer.py)
□ 编写单元测试
```

### Phase 3: NLU + API (Week 4)

```
□ 实现规则式 NLU (正则 + 关键词匹配)
□ 实现 FastAPI 接口
   □ POST /api/query/name       (名称查询)
   □ POST /api/query/suitability (属性查询)
   □ GET  /api/pal/:id/breeding-tree (配种树)
□ API 文档自动生成 (Swagger)
```

### Phase 4: 前端 UI (Week 5-6)

```
□ React/Vue 项目初始化
□ 搜索输入组件 (支持打字)
□ 候选列表组件
□ 配种树可视化组件 (D3.js/ECharts)
□ 语音输入集成 (Web Speech API)
```

### Phase 5: 增强 + 部署 (Week 7+)

```
□ LLM 增强 NLU (可选接入大模型做意图理解)
□ 语音识别优化 (Whisper 本地部署)
□ Docker 容器化
□ CI/CD 自动测试
□ 数据自动更新检测
```

---

## 10. 风险与对策

| 风险 | 等级 | 对策 |
|------|:---:|------|
| paldb.cc 改版导致爬虫失效 | 🔴 高 | 爬虫层独立封装，解析规则配置化；备选游戏文件解包方案 |
| 游戏更新后 CombiRank 大幅调整 | 🟡 中 | 数据版本化管理；diff 对比工具；保留历史版本 |
| 特殊配种规则遗漏 | 🟡 中 | 参考 paldb.cc 的 Breed Tree 结果交叉验证 |
| 配种树过深影响性能 | 🟢 低 | BFS + 缓存中间结果；限制最大深度 |
| 中文语音识别准确率 | 🟡 中 | MVP 用文本输入；语音降级为辅助功能 |
| "手工10级"实际不存在 (当前最高6级) | 🟡 中 | 返回实际最高等级 + "接近"的帕鲁推荐 |

---

> 📌 **下一步建议**：确认架构后，开始 Phase 1 — 编写 paldb.cc 数据爬虫脚本，跑通第一条数据链路。
