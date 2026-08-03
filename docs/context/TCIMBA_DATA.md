# tc-imba 数据源清单

> 数据源: [palworld.tc-imba.com](https://palworld.tc-imba.com/)（玩家自建、从游戏文件提取）
> 数据接口: `https://data-palworld.tc-imba.com/`
> 本文档基于 2026-08 抓取验证。

## 1. 数据文件总览

| 文件 | 大小 | 条目数 | 内容 |
|------|------|--------|------|
| `version.json` | 62B | - | 数据版本 (`version` / `gameVersion`) |
| `pals.json` | 1.3MB | 299 帕鲁 | 帕鲁完整属性 |
| `breeding.json` | 82KB | 299 pals + 250 combos | 配种 rank / breedChild / 独特组合 |
| `passives.json` | 27KB | 115 被动 | 被动技能数据（可获取；zh_passives 152 含装备被动）|
| `items.json` | 2.0MB | 2433 物品 | 物品数据（含配方/来源/掉落） |
| `locales/zh-CN/pals.json` | 140KB | 299 | 帕鲁中文名/描述/伙伴技能 |
| `locales/zh-CN/passives.json` | 16KB | 152 | 被动技能中文名 |
| `locales/zh-CN/skills.json` | 59KB | 323（可学习 319）| 技能中文名+描述 |
| `locales/zh-CN/items.json` | 418KB | 2433 | 物品中文名+描述 |
| `locales/zh-CN/enums.json` | 601B | - | 元素/工种枚举中文名 |
| `locales/zh-CN/partnerEffects.json` | 已确认存在 | - | 伙伴技能效果名（{effectId: 中文名}）|
| `locales/zh-CN/partnerTargets.json` | 已确认存在 | - | 伙伴技能目标名 |
| `locales/en-US/*.json` | - | - | 英文版同名文件 |

> **注意**: 根路径下的 `skills.json` / `enums.json` / `partnerEffects.json` / `partnerTargets.json` **不存在（404）**。
> 技能/枚举/伙伴效果**只有本地化版本**（`locales/zh-CN/` 下已确认存在），数据本体内嵌在 `pals.json`（`activeSkills` / `partnerSkill`）。
> **图标资源**: `https://resource-palworld.tc-imba.com/icons/{icon}.webp`（已实测有效，128×128 webp）。

## 2. 各文件结构详解

### 2.1 `version.json`
```json
{ "version": "xxx", "gameVersion": "0.4.x" }
```

### 2.2 `pals.json` — 帕鲁属性（299）
```json
{
  "pals": [
    {
      "id": "SheepBall",
      "zukanIndex": 1, "zukanIndexSuffix": "",
      "icon": "T_SheepBall_icon_normal",
      "elements": ["Normal"],
      "genus": "Humanoid", "size": "XS",
      "rarity": 1,
      "egg": "PalEgg_Normal_01",
      "nocturnal": false, "reaction": "Friendly",
      "stats": {
        "hp": 70, "meleeAttack": 70, "shotAttack": 70, "defense": 70,
        "support": 100, "craftSpeed": 100, "stamina": 100,
        "foodAmount": 1, "maxFullStomach": 100,
        "captureRate": 1.5, "expRatio": 1, "price": 421,
        "maleProbability": 50,
        "slowWalkSpeed": 23, "walkSpeed": 40, "runSpeed": 400,
        "rideSprintSpeed": 550, "transportSpeed": 160, "swimSpeed": 120
      },
      "friendship": { "hp": 5.5, "shotAttack": 3.7, "defense": 3.7 },
      "enemyScaling": { "receiveDamage": 2 },
      "work": { "Handcraft": 1, "Transport": 1, "MonsterFarm": 1 },
      "bestWork": "MonsterFarm",
      "partnerSkill": { "action": { ... } },
      "activeSkills": [ { "wazaId": "StoneShotgun", "level": 1, "element": "Earth",
                          "category": "Shot", "power": 80, "coolTime": 4,
                          "minRange": 500, "maxRange": 4000, "strength": "Weak",
                          "effect": {"type": "Muddy", "value": 100} } ],
      "passives": ["ElementBoost_Earth_2_PAL"],
      "drops": [ { "item": "Bone", "rate": 100, "min": 3, "max": 5 } ],
      "bossDrops": [ ... ],
      "summonable": false,
      "predator": false,
      "bossFirstDefeatReward": "BossDefeatReward_PlantSlime",
      "summonLevel": 55,
      "summonMaterials": [ { "item": "PalSummon_KingBahamut_Dragon_Parts", "count": 4 } ]
    }
  ],
  "filters": [ ... ]
}
```
- `elements`: 元素（Normal/Fire/Water/Leaf/Electricity/Ice/Earth/Dark/Dragon）
- `work`: 工作适应性（12 种，值 0-10），`bestWork` 为最高项
- `stats`: 基础属性（HP/攻击/防御/速度/捕获率/价格/雄性概率等）
- `activeSkills`: 该帕鲁可习得的技能（含**学习等级**，用于技能表 + pal_skill）
- `passives`: 该帕鲁固有被动
- `drops` / `bossDrops`: 击杀掉落（含概率/数量/最低等级），可反查材料来源。⚠ 两者物品有重叠，需区分普通/Boss
- `predator`: 是否捕食者（主动攻击，实测 65 只）
- `summonLevel` / `summonMaterials`: Boss 召唤等级与材料（数组 {item, count}）
- `bossFirstDefeatReward`: Boss 首杀奖励 key（对应本地化）

### 2.3 `breeding.json` — 配种（299 pals + 250 combos）
```json
{
  "pals": [ { "id": "SheepBall", "zukanIndex": 1, "zukanIndexSuffix": "",
              "icon": "...", "rank": 3050, "dup": 305000, "idx": 378,
              "breedChild": true } ],
  "combos": [ { "a": "YakushimaMonster001", "b": "YakushimaMonster001",
                "c": "YakushimaMonster001" } ]
}
```
- `pals[].rank`: 配种等级（用于 rank 平均公式）
- `pals[].breedChild`: `false` = 只能通过独特组合获得（不可作为 rank 平均结果）
- `combos[]`: 250 条独特组合（`a×b → c`），其中 114 same_species + 136 fixed_pair

### 2.4 `passives.json` — 被动技能（115）
```json
{ "passives": [
  { "id": "CraftSpeed_up3", "rank": 4,
    "effects": [ { "type": "CraftSpeed", "value": 75, "target": "ToSelf" } ],
    "invoke": ["always"], "lotteryWeight": 5 }
] }
```
- `effects[].type/value`: 效果类型与数值（如 CraftSpeed +75）
- `lotteryWeight`: 遗传抽奖权重（配种被动传承）

### 2.5 `items.json` — 物品（2433）
```json
{ "items": [
  { "id": "Money", "typeA": "Material", "typeB": "Money", "sortId": 0,
    "rarity": 0, "rank": 1, "weight": 0, "price": 1, "maxStack": 99999999,
    "handcraft": false,
    "recipe": { "work": 2000000, "materials": [ { "item": "CopperIngot", "count": 30 } ],
                "productCount": 20000, "craftedAt": ["Factory_Money"] },
    "sources": [ { "kind": "chest", "area": "DarkIsland", "grade": 1, "chance": 100 } ],
    "droppedBy": [...], "usedInItems": [...], "icon": "..." }
] }
```
- 可选字段: `recipe`(1394) / `sources`(865) / `droppedBy`(149) / `usedInItems`(439) /
  `unlockTech`(380) / `equip`(728) / `itemPassives`(192) / `food`(158) / `foodBuff`(53) /
  `usedInBuildings`(56) / `grantsSkill`(93) / `unlocksCraft`(571) / `partnerFor`(140)

### 2.6 本地化文件（`locales/zh-CN/`）
| 文件 | 结构 | 示例 |
|------|------|------|
| `pals.json` | `{id: {name, description, partnerSkill}}` | `SheepBall → {name: "绵悠悠", ...}` |
| `passives.json` | `{id: {name}}` | `CraftSpeed_up3 → {name: "卓绝技艺"}` |
| `skills.json` | `{id: {name, description}}` | `AirBlade → {name: "真空刃", ...}` |
| `items.json` | `{id: {name, description}}` | 2433 物品中文名 |
| `enums.json` | `{elements: {...}, work: {...}}` | 元素/工种中文名 |
| `partnerEffects.json` | `{id: {name}}` | 伙伴技能效果名 |
| `partnerTargets.json` | `{id: {name}}` | 伙伴技能目标名 |

## 3. 系统当前已用的数据

| 数据 | 用途 | 接入路径 |
|------|------|----------|
| `breeding.json` combos | `breeding_rule` 表（same_species/fixed_pair） | `scripts/seed_breeding_rules.py` |
| `breeding.json` pals + `pals.json` | `pal` 表（rank / breed_child / 属性 / 工作 / 元素） | `scripts/convert_tcimba.py` → `pal_data.json` → PG |
| `locales/zh-CN/pals.json` | `pal_aliase` 中文名 | `scripts/convert_tcimba.py` |
| `locales/zh-CN/enums.json` | 元素/工种中文映射（映射逻辑内置于 convert 脚本） | `scripts/convert_tcimba.py` |

## 4. 候选数据 — 已全部接入（22 表，P0-P6 完成）

> ✅ 本节所列的候选数据（被动/技能/掉落/物品/属性/伙伴技能）**现已全部接入**数据库，
> 对应 22 表设计与 S6-S10 查询见
> [`architecture/design/DATABASE_DESIGN_TCIMBA_V2.md`](../architecture/design/DATABASE_DESIGN_TCIMBA_V2.md)
> 与 [`architecture/plans/TCIMBA_DATA_DEVELOPMENT_PLAN.md`](../architecture/plans/TCIMBA_DATA_DEVELOPMENT_PLAN.md)。

| 数据 | 落地表 |
|------|--------|
| 被动技能 `passives.json` + `zh-CN/passives.json` | `passive` + `passive_effect` + `passive_invoke` + `pal_passive` |
| 技能 `pals[].activeSkills` + `zh-CN/skills.json` | `skill` + `pal_skill`（level） |
| 帕鲁掉落 `pals[].drops` / `bossDrops` | `pal_drop`（item/rate/min/max/minLevel） |
| 物品 `items.json` + `zh-CN/items.json` | `item` + `item_source` + `item_recipe` + `item_recipe_station` + `item_recipe_material` |
| 帕鲁基础属性 `pals[].stats` | `pal_stats` |
| 伙伴技能 `pals[].partnerSkill` | `pal_partner_skill` |
| 其他扩展 | `pal_friendship` / `pal_enemy_scaling` / `pal_summon` / `pal` 扩展列 |

> ⚠️ **尚未接入**（见 [`decisions/003-feature-gaps.md`](../decisions/003-feature-gaps.md)）：
> 地图/坐标、科技树、属性模拟器(IV)、多代配种规划 —— 这些**数据源不在此 13 文件内**，需额外数据源。

## 5. 抓取方式（参考）

```bash
BASE="https://data-palworld.tc-imba.com"
# 核心数据
for f in version.json breeding.json pals.json passives.json items.json; do
  curl -s -m 30 "$BASE/$f" -o "data/tc-imba/$f"
done
# 本地化
for f in pals passives skills items enums partnerEffects partnerTargets; do
  curl -s -m 30 "$BASE/locales/zh-CN/$f.json" -o "data/tc-imba/zh_$f.json"
done
```
