# ADR 003: 数据源网站功能差距清单（后续开发）

> 日期: 2026-08-02 | 状态: 已记录（待排期开发） | 决策者: AI + 用户

---

## 背景

对数据源网站 [palworld.tc-imba.com](https://palworld.tc-imba.com/)（v1.23.0）做了全功能盘点，
与我们的 agent（10 工具 + Text-to-SQL 兜底）逐一比对。绝大多数模块已覆盖，但存在 **4 项差距**，
本 ADR 记录差距详情，供后续排期开发。

## 差距清单

### ① 地图 `/`（完全无数据）

- **网站功能**: 地点 / 首领 / 区域头目 / 悬赏头目 / 狂暴化 / 地下城 / 高塔 / 据点 /
  封印领域 / 远古神龛 / 传送环 / 收集品（藏宝图 / 笔记 / 技能果实 / 帕鲁蛋 / 宝箱 / 垂钓场 / 补给物资 / 油田要塞）
- **现状**: 数据库无任何地点/地图相关表；`run_sql_query` 也救不了（没有数据表）
- **数据来源建议**: `data-palworld.tc-imba.com` 地图数据（需调研 URL），或手工整理
- **开发优先级**: 低（玩家主要用配种）

### ② 科技树 `/technology`（完全无数据）

- **网站功能**: 588 项科技，分 科技 / 古代科技 两大类，按等级（1/2/3...）解锁，
  每项含 类别（建筑/道具）+ 消耗点数
- **现状**: 数据库无科技表。注意：科技解锁的**配方**其实部分已藏在 `item_recipe` 中
  （如 石头斧 / 帕鲁球），但"科技树结构 / 解锁等级 / 点数"无数据
- **数据来源建议**: 从 tc-imba 站点数据结构化提取，新增 `technology` / `technology_unlock` 表
- **开发优先级**: 中（可与物品配方打通，回答"xx 科技几级解锁"）

### ③ 属性模拟器 `/stat-simulator`（无计算能力）

- **网站功能**: 根据强化状态精确计算任意帕鲁的游戏内属性；也可输入游戏内属性**反推隐藏个体值(IV)**
- **现状**: `pal_stats` 只有基础属性值（hp/攻/防/速度/捕获率），
  无 IV 生成/反推公式、无强化(condense/等级)成长计算
- **数据来源建议**: 调研帕鲁属性成长公式 + 需要完整成长曲线数据
- **开发优先级**: 低（偏工具型，与配种 agent 定位弱相关）

### ④ 多代配种规划 `/breeding` 多代计划（部分覆盖）

- **网站功能**: 支持"多代计划"——从目标子代反推整条**多代配种链**（A+B→C, C+D→E...）
- **现状**: `query_parent_pairs` 只支持**单代**直接父母组合查询，无递归/多代链路生成
- **数据来源建议**: 纯逻辑增强——基于现有 `combi_rank` + `breeding_rule` 做 BFS 深度搜索
- **开发优先级**: **高**（与配种 agent 定位最契合，改动最小收益最大）

## 覆盖确认（已覆盖模块）

| 网站模块 | Agent 工具 | 数据表 |
|---------|-----------|--------|
| 帕鲁图鉴 /pals | `resolve_pal` / `query_pal_detail` / `query_top_suitability` | pal / pal_stats / work_suitability |
| 配种配方 /breeding | `query_parent_pairs` | pal.combi_rank / breeding_rule |
| 道具 /items | `query_item_recipe` / `query_item_drops` | item / item_recipe / pal_drop |
| 被动技能 /passives | `query_pals_by_passive` | passive / pal_passive |
| 主动技能 /active-skills | `query_pal_skills` | skill / pal_skill |
| 伙伴技能 /partner-skills | `query_pal_detail`（含 partner_skill） | pal_partner_skill |
| 任意组合查询 | `run_sql_query` | v_pal_full / v_item_drop / v_skill_learn |

## 后续开发建议顺序

1. **④ 多代配种**（纯逻辑，现有数据即可做，BFS）
2. **② 科技树**（新增表，抓 tc-imba 数据）
3. **① 地图**（新增表，需调研数据源）
4. **③ 属性模拟器**（需公式研究，最重）
