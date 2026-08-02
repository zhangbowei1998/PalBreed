import type { DataCard } from "../types";

/** 渲染 Agent 工具返回的结构化数据卡片（被动/掉落/配方/技能/详情）。 */
export default function DataCardList({ cards }: { cards: DataCard[] }) {
  if (!cards || cards.length === 0) return null;
  return (
    <div className="data-card-list">
      {cards.map((card, i) => (
        <DataCardItem key={i} card={card} />
      ))}
    </div>
  );
}

function DataCardItem({ card }: { card: DataCard }) {
  switch (card.type) {
    case "passive":
      return (
        <div className="data-card">
          <div className="data-card-title">
            拥有「{card.passive}」的帕鲁
            {card.total > 0 && <span className="data-card-count">{card.total}</span>}
          </div>
          <ul className="data-card-body">
            {(card.pals ?? []).slice(0, 12).map((p, i) => (
              <li key={i}>{p.cn_name ?? p.id ?? "?"}</li>
            ))}
            {card.total > 12 && <li className="data-card-more">…共 {card.total} 只</li>}
          </ul>
        </div>
      );
    case "drop":
      return (
        <div className="data-card">
          <div className="data-card-title">
            「{card.item}」掉落来源
            {card.total > 0 && <span className="data-card-count">{card.total}</span>}
          </div>
          <ul className="data-card-body">
            {(card.pals ?? []).slice(0, 12).map((p, i) => (
              <li key={i}>
                {p.pal_cn ?? p.pal_id ?? "?"}
                {p.is_boss && <span className="data-card-tag">Boss</span>}
              </li>
            ))}
            {card.total > 12 && <li className="data-card-more">…共 {card.total} 只</li>}
          </ul>
        </div>
      );
    case "recipe":
      return (
        <div className="data-card">
          <div className="data-card-title">「{card.item}」制作配方</div>
          <ul className="data-card-body">
            {(card.recipe ?? []).map((r, i) => (
              <li key={i}>
                {r.material ?? "?"} × {r.count ?? 1}
                {r.station && <span className="data-card-tag">{r.station}</span>}
              </li>
            ))}
          </ul>
        </div>
      );
    case "skills":
      return (
        <div className="data-card">
          <div className="data-card-title">
            {card.pal?.cn_name ?? card.pal?.id ?? "?"} 可学技能
            {card.total > 0 && <span className="data-card-count">{card.total}</span>}
          </div>
          <ul className="data-card-body">
            {(card.skills ?? []).map((s, i) => (
              <li key={i}>
                {s.cn_name ?? s.waza_id ?? "?"}
                {s.element && <span className="data-card-tag">{s.element}</span>}
                <span className="data-card-lv">Lv{s.learn_level ?? 1}</span>
              </li>
            ))}
          </ul>
        </div>
      );
    case "pal_detail":
      return (
        <div className="data-card">
          <div className="data-card-title">{card.cn_name ?? card.pal_id ?? "帕鲁详情"}</div>
          <div className="data-card-body data-card-detail">
            {card.stats && typeof card.stats.hp === "number" && (
              <span>HP {card.stats.hp} · 攻 {card.stats.melee_attack ?? "-"} · 防 {card.stats.defense ?? "-"}</span>
            )}
            <span>
              技能 {card.skill_count ?? 0} · 掉落 {card.drop_count ?? 0}
            </span>
          </div>
        </div>
      );
    default:
      return null;
  }
}
