# 核心引擎需求文档 (已归档)

> 版本: v1.2 | 日期: 2026-08-04 | 状态: **已废弃 ⛔**

> ⚠️ **本文档已归档。** v0.2 起核心引擎层 (breeding_engine, breeding_tree, suitability_query, path_optimizer, interfaces) 已全部移除。配种计算现由 API ORM 查询服务完成（`packages/api/pl_agent/api/routes/query.py` + `packages/api/pl_agent/api/db/queries.py`）。参考 `ARCHITECTURE.md` §4 了解当前实现。

---

## 目录

1. [概述与目标](#1-概述与目标)
2. [模块架构](#2-模块架构)
3. [配种计算引擎](#3-配种计算引擎)
4. [配种树构建器](#4-配种树构建器)
5. [属性查询器](#5-属性查询器)
6. [路径择优器](#6-路径择优器)
7. [数据输入/输出规格](#7-数据输入输出规格)
8. [异常与边界情况](#8-异常与边界情况)
9. [验收标准](#9-验收标准)

---

## 1. 概述与目标

### 1.1 定位

核心引擎是系统的大脑。它接收结构化查询，输出配种方案。引擎本身是**纯算法**——不涉及网络 I/O、不解析非结构化文本、不渲染 UI。

### 1.2 模块清单

| 模块 | 文件 | 职责 |
|------|------|------|
| 配种计算引擎 | `breeding_engine.py` | 正向/反向 CombiRank 配种计算 |
| 配种树构建器 | `breeding_tree.py` | BFS 反向搜索 + 递归展开 |
| 属性查询器 | `suitability_query.py` | 按工作适应性筛选帕鲁 |
| 路径择优器 | `path_optimizer.py` | 多条配种路径排序 |

### 1.3 核心约束

- **纯算法**：不依赖 HTTP、数据库。输入 `list[Pal]`，输出结构体。
- **Schema 严格**：所有 Pal 实体使用 `pl_agent.core.schema.Pal`。
- **异常规范**：业务异常全部来自 `pl_agent.core.errors`。
- **基础帕鲁**：`is_wild == True` 的帕鲁，是配种树的叶子节点。

---

## 2. 模块架构

```
用户查询
   │
   ▼
┌──────────────┐    ┌──────────────────┐
│ 属性查询器     │    │  配种计算引擎      │
│ suitability  │    │  breeding_engine  │
│ _query.py    │    │  .py              │
│              │    │                   │
│ 输入:        │    │ forward(父, 母)    │
│  work_type   │    │ reverse(子)       │
│  min_level   │    │ reverse_with_     │
│              │    │ parent(子, 父)    │
│ 输出:        │    │                   │
│  list[Pal]   │    │ 输出:             │
└──────┬───────┘    │ list[(父, 母)]    │
       │            └────────┬─────────┘
       │                     │
       ▼                     ▼
┌──────────────────────────────────────┐
│          配种树构建器                  │
│          breeding_tree.py            │
│                                      │
│  build(target, max_depth=5)         │
│       │                              │
│       ├── BFS 反向搜索所有父母对        │
│       ├── 递归展开每个父母             │
│       ├── visited 去重防循环           │
│       └── 生成 BreedingTree          │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│          路径择优器                    │
│          path_optimizer.py           │
│                                      │
│  optimize(tree) → tree.best_path     │
│  排序: 步数 > 基础帕鲁数 > 稀有度       │
└──────────────────────────────────────┘
```

---

## 3. 配种计算引擎

### 3.1 正向计算：父母 → 子代

```
函数签名:
  forward_breed(parent_a: Pal, parent_b: Pal) -> Pal

算法流程:
  ┌─────────────────────────────────────┐
  │ 1. 查特殊组合表 (special_combinations)│
  │    if (a, b) 命中特殊组合 → 直接返回  │
  ├─────────────────────────────────────┤
  │ 2. 查 self_only 表                   │
  │    if a == b && a 是传说 → 返回 a     │
  ├─────────────────────────────────────┤
  │ 3. 标准 CombiRank 计算               │
  │    target = round((a.rank + b.rank) / 2)
  │    child = 最接近 target 的 Pal       │
  │    等距时优先图鉴编号小的               │
  │    同值时取 CombiRank 等于 target 的     │
  └─────────────────────────────────────┘

特殊情况:
  - 父代在 unbreedable 列表中 → 仍可正常计算 (不可配种指子代, 不是父代)
  - 父代在 breeding_excluded 中 → 拒绝计算, 抛出 DataIntegrityError
```

**示例**：

```python
# 棉悠悠(CombiRank=1470) + 捣蛋猫(CombiRank=1460)
# target = round((1470+1460)/2) = 1465
# 最接近 1465 的 Pal → 捣蛋猫(Cattiva, rank=1460)
forward_breed(Lamball, Cattiva) → Cattiva
```

### 3.2 反向计算：子代 → 所有可能父母对

```
函数签名:
  reverse_breed(child: Pal) -> list[tuple[Pal, Pal]]

算法流程:
  ┌─────────────────────────────────────┐
  │ 1. 查 special_combinations          │
  │    if child 由特殊组合产生 →         │
  │    返回 [(self,self)] + 固定父母对    │
  ├─────────────────────────────────────┤
  │ 2. 查 self_only                     │
  │    if child 是传说 →                 │
  │    返回 [(child, child)]            │
  ├─────────────────────────────────────┤
  │ 3. 查 unbreedable + breeding_excluded│
  │    if child 不可配种或排除 → 返回 []  │
  ├─────────────────────────────────────┤
  │ 4. 找 child 前后的 CombiRank 帕鲁     │
  │    prev: CombiRank 刚好 <= child 的   │
  │    next: CombiRank 刚好 >= child 的   │
  │    排除 breeding_excluded 中的帕鲁    │
  ├─────────────────────────────────────┤
  │ 5. 确定父母 power 总和区间            │
  │    sum_low = child.rank + prev.rank  │
  │    sum_high = child.rank + next.rank │
  ├─────────────────────────────────────┤
  │ 6. 枚举 CombiRank 组合               │
  │    对 (pal_a, pal_b) 组合:           │
  │      排除 breeding_excluded 中的帕鲁  │
  │      sum = a.rank + b.rank          │
  │      if sum 在有效区间内              │
  │        round(sum/2) == child.rank   │
  │      → 加入结果列表                   │
  └─────────────────────────────────────┘

去重:
  - (a, b) 与 (b, a) 视为同一对，只保留一种
  - 排除 a == b == child 的情况 (循环)
  - 如果 prev 或 next 有多个同值帕鲁，任取其一即可 (结果等价)
```

**区间判断规则**：

```
设 prev=child 前面最近的帕鲁, next=child 后面最近的帕鲁
child_index = index_list.index(child.en_name)
prev_index  = index_list.index(prev.en_name)
next_index  = index_list.index(next.en_name)

prev_equal = (prev_index >= child_index)  # 闭区间
next_equal = (next_index >= child_index)  # 闭区间

父母 power 总和区间:
  下界: prev_sum = child.rank + prev.rank
  上界: next_sum = child.rank + next.rank
  包含判断:
    prev_equal → sum >= prev_sum (闭)
   !prev_equal → sum >  prev_sum (开)
    next_equal → sum <= next_sum (闭)
   !next_equal → sum <  next_sum (开)
```

### 3.3 反向+筛选：子代 + 一方父母 → 另一方

```
函数签名:
  reverse_with_parent(child: Pal, parent: Pal) -> list[Pal]

算法:
  1. 调用 reverse_breed(child) 获取全部父母对
  2. 筛选包含 parent 的对
  3. 返回另一方的 Pal 列表
```

---

## 4. 配种树构建器

### 4.1 核心算法：BFS + 递归展开

```
函数签名:
  build_breeding_tree(
      target: Pal,
      max_depth: int = 5,
      allow_wild_only_leaves: bool = True
  ) -> BreedingTree
```

### 4.2 算法流程

```
build_breeding_tree(target):
  │
  ├── 1. 初始化 parent_map: dict[Pal, list[(Pal, Pal)]] = {}
  │      visited = set()
  │
  ├── 2. BFS 遍历构建 parent_map:
  │   │
  │   ├── 队列: queue = [(target, 0)]
  │   │
  │   ├── while queue 非空:
  │   │   ├── 取出 (current_pal, depth)
  │   │   │
  │   │   ├── 终止条件:
  │   │   │   ├── current_pal.is_wild → 叶子, 不入 parent_map
  │   │   │   ├── depth >= max_depth → 截断, 标记 _truncated
  │   │   │   ├── current_pal in visited → 跳过
  │   │   │   └── current_pal 不可配种 → 叶子
  │   │   │
  │   │   ├── 调用 reverse_breed(current_pal)
  │   │   ├── 存储: parent_map[current_pal] = 父母对列表
  │   │   ├── 将每对父母 (a, b) 加入队列 (depth+1)
  │   │   └── visited.add(current_pal)
  │   │
  │   └── 如果 current_pal 无父母对 → 标记为叶子
  │
  ├── 3. 从 parent_map 回溯构建 BreedingPath 列表:
  │   │
  │   └── 递归函数 backtrack(pal) -> list[BreedingPath]:
  │       ├── if pal.is_wild or pal not in parent_map:
  │       │   → 返回单步路径 [BreedingPath(steps=[], leaf_pals=[pal])]
  │       │
  │       └── for 每对 (a, b) in parent_map[pal]:
  │           ├── 递归: left_paths = backtrack(a), right_paths = backtrack(b)
  │           ├── 组合: left × right → 产生新 BreedingPath
  │           └── 合并 leaf_pals, 累加 total_steps
  │
  ├── 4. 去重优化:
  │     ├── 同一 Pal 出现在单个路径中多次 → 保留第一个, 截断
  │     └── 相同路径 (相同 steps 列表) → 只保留一条
  │
  └── 5. 组装 BreedingTree 返回
```

### 4.3 数据结构

```python
@dataclass
class BreedingStep:
    """配种的一个步骤"""
    parent_a: Pal          # 父代 A
    parent_b: Pal          # 父代 B
    child: Pal             # 产出子代
    method: str            # "wild"(野外捕获) | "breed"(配种)

@dataclass
class BreedingPath:
    """一条完整的配种路径 (从基础帕鲁到目标)"""
    steps: list[BreedingStep]
    leaf_pals: list[Pal]       # 需要从野外捕获的基础帕鲁
    total_steps: int = 0       # 配种步骤数 (steps 中去重后的数量)
    avg_rarity: float = 0.0    # 叶子帕鲁平均稀有度

@dataclass
class BreedingTree:
    """配种树"""
    target: Pal
    paths: list[BreedingPath]
    best_path: BreedingPath | None
    total_paths: int
    max_depth_reached: int

    def to_dict(self) -> dict:
        """JSON 序列化"""
        ...
```

### 4.4 配种树输出示例

```
目标: 阿努比斯 (CombiRank=480)

路径 1 (2步, 最优):
  🌿 棉悠悠 (野生)  +  🌿 捣蛋猫 (野生)
           │
        🥚 疾旋鼬     +  🌿 烽歌龙 (野生)
           │                │
           └───────┬────────┘
                   │
               🎯 阿努比斯

路径 2 (3步):
  🌿 棉悠悠 (野生) + 🌿 夜幕魔蝠 (野生)
           │
        🥚 霹雳犬      + 🌿 烽歌龙 (野生)
           │                │
           └───────┬────────┘
                   │
               🥚 雷隐鹿      + 🌿 烽歌龙 (野生)
                   │                │
                   └───────┬────────┘
                           │
                       🎯 阿努比斯
```

---

## 5. 属性查询器

### 5.1 单条件查询

```
函数签名:
  query_by_suitability(
      work_type: str,       # "handiwork" / "kindling" / ...
      min_level: int = 1
  ) -> list[tuple[Pal, int]]
```

**流程**：

```
1. 遍历所有 Pal
2. 筛选 work_suitability[work_type] >= min_level
3. 按等级降序排序
4. 返回 (Pal, 实际等级)
```

**辅助查询**：

```python
# 获取指定工种的最高等级
get_max_level("handiwork") → 6

# 获取所有工种统计
get_level_stats() → {"handiwork": {"max": 6, "avg": 2.1}, ...}
```

### 5.2 多条件查询

```
函数签名:
  query_by_multi_suitability(
      requirements: list[tuple[str, int]]
  ) -> list[tuple[Pal, int]]
```

**流程**：筛选同时满足所有工种条件的帕鲁。返回的 `int` 为各条件中满足的最低等级。

**示例**：
```python
# 查询"既会手工(≥3)又会采矿(≥3)"的帕鲁
query_by_multi_suitability([
    ("handiwork", 3),
    ("mining", 3),
])
# → [(阿努比斯, 6), (焰皇, 5), (唤夜兽, 4), ...]
```

### 5.3 查询结果超出范围处理

引擎不做用户交互。当 `min_level` 超过数据集中的最高等级时：

```python
result = query_by_suitability("handiwork", 10)
# → []  (空列表)

# 引擎同时可通过附加 API 获取统计信息:
max_level = engine.get_max_level("handiwork")
# → 6
```

**调用的上层**（NLU/API）负责判断：
- 如果结果为空且 `min_level > max_level` → 生成提示 "手工最高 Lv6，已为您展示所有手工帕鲁"
- 如果结果为空且 `min_level <= max_level` → "无符合条件的结果"

---

## 6. 路径择优器

### 6.1 排序策略

```
函数签名:
  optimize(tree: BreedingTree) -> BreedingTree
```

**评分公式**（越低越好）：

```
score(path) = total_steps × 100   # 步数惩罚 (主指标)
            + len(leaf_pals) × 10  # 需要抓的帕鲁总数
            + avg_rarity × 1       # 叶子帕鲁平均稀有度 (副指标)
```

### 6.2 排序规则（优先级从高到低）

| 优先级 | 规则 | 说明 |
|:---:|------|------|
| 1 | 步数最少 | `total_steps` 升序 |
| 2 | 基础帕鲁最少 | `leaf_pals` 数量升序 |
| 3 | 稀有度最低 | `avg_rarity` 升序 |
| 4 | 不含传说/Boss | 路径中不含 `self_only` 或 `unbreedable` 列表中的帕鲁 |
| 5 | 最先发现 | 同等条件下 BFS 先发现的优先 |

### 6.3 输出

```
1. 标记 tree.best_path = 最优路径
2. 标记 tree.paths = 按评分排序后的所有路径
3. 返回优化后的 tree
```

---

## 7. 数据输入/输出规格

### 7.1 输入

所有函数通过 DataLoader 获取数据：

```python
from pl_agent.core.data_loader import DataLoader

loader = DataLoader()
loader.load("data/processed/pal_data.json")

# 引擎初始化
engine = BreedingEngine(
    pals=loader.get_all_sorted_by_rank(),
    rules=breeding_rules,       # BreedingRules 实例
    wild_ids={p.id for p in loader.get_wild_pals()},
)
```

### 7.2 输出

所有输出使用 dataclass，可直接 JSON 序列化：

```python
tree = builder.build(target_pal)
print(tree.to_dict())
# {
#   "target": {"id": "Anubis", "cn_name": "阿努比斯", ...},
#   "best_path": {
#     "total_steps": 2,
#     "steps": [
#       {"parent_a": {...}, "parent_b": {...}, "child": {...}, "method": "breed"},
#       ...
#     ],
#     "leaf_pals": [{"id": "Lamball", ...}, {"id": "Cattiva", ...}]
#   },
#   "paths": [...],
#   "total_paths": 5,
#   "max_depth_reached": 4
# }
```

---

## 8. 异常与边界情况

### 8.1 异常映射

| 场景 | 异常 | 处理 |
|------|------|------|
| Pal 不在数据集中 | `PalNotFoundError` | 直接抛出 |
| CombiRank 为 0 或负数 | `DataIntegrityError` | 记录并跳过 |
| 配种树中检测到循环 | `BreedingLoopError` | 截断该分支, 不阻塞整棵树 |
| 特殊组合中的 Pal ID 不存在 | `DataIntegrityError` | 跳过该规则, 记录 warning |
| max_depth 到达但未到叶子 | (正常) | 截断, 标记 `_truncated: True` |
| 无任何配种路径 | 返回空 Tree | `tree.paths = []` |
| 用户查询不存在的工种 | `PalNotFoundError` | "未知的工种类型: xxx" |

### 8.2 边界情况

| 场景 | 处理 |
|------|------|
| 目标本身就是基础帕鲁 | 返回单节点树: `[{target, method="wild"}]` |
| 所有叶子都是传说帕鲁 | 路径仍有效, 但评分会偏低 (稀有度高) |
| 子代 = 父代之一 (如传说帕鲁) | 反向计算时返回 `[(self, self)]` |
| BFS 搜索空间爆炸 (深度>5) | 硬截断, max_depth 默认 5 |
| 同一帕鲁可被多对父母产出 | 全部保留, 由 PathOptimizer 排序 |

---

## 9. 验收标准

### 9.1 配种计算引擎

- [ ] `forward_breed` 验证: Lamball + Cattiva → 正确子代 (参考 paldb.cc 验证)
- [ ] `forward_breed` 特殊组合: Relaxaurus + Sparkit → Relaxaurus Lux
- [ ] `forward_breed` 传说: Frostallion + Frostallion → Frostallion
- [ ] `reverse_breed` Anubis → 返回 ≥ 10 对可能父母，全部不含 breeding_excluded 中的帕鲁
- [ ] `reverse_breed` Frostallion → 返回 `[(Frostallion, Frostallion)]`
- [ ] `reverse_breed` 不可配种 Pal → 返回 `[]`
- [ ] `reverse_with_parent` 验证: Anubis + Fenglope_Lux → 正确返回另一方

### 9.2 配种树构建器

- [ ] Anubis 配种树构建成功, 深度 ≤ 5
- [ ] 配种树中所有叶子节点都是 `is_wild=True` 的帕鲁
- [ ] 无循环依赖 (同一 Pal 不在同一分支出现两次)
- [ ] max_depth=1 时正确截断
- [ ] 基础帕鲁作为目标 → 单节点树

### 9.3 属性查询器

- [ ] `query_by_suitability("handiwork", 6)` 返回包含阿努比斯等的结果
- [ ] `query_by_suitability("handiwork", 100)` 返回 `[]`，`get_max_level("handiwork")` 返回实际最高值
- [ ] `query_by_multi_suitability([("handiwork", 3), ("mining", 3)])` 返回 `list[tuple[Pal, int]]`
- [ ] 查询不存在的工种 → 抛出 `PalNotFoundError`

### 9.4 路径择优器

- [ ] 按步数排序正确
- [ ] 同等步数按基础帕鲁数排序
- [ ] 最优路径 ≤ 最短路径
