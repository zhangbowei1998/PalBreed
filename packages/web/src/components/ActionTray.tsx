import type { AgentAction } from "../types";

type Props = {
  actions: AgentAction[];
  loading: boolean;
  onAction: (action: AgentAction) => Promise<void>;
  onSummarize: () => Promise<void>;
  canSummarize: boolean;
};

export function ActionTray({ actions, loading, onAction, onSummarize, canSummarize }: Props) {
  return (
    <section className="action-tray">
      <div className="action-row">
        {actions.map((item, idx) => (
          <button key={`${item.action}-${idx}`} onClick={() => onAction(item)} disabled={loading}>
            {item.label}
          </button>
        ))}
      </div>
      <button className="route-btn" onClick={onSummarize} disabled={loading || !canSummarize}>
        生成配种路线
      </button>
    </section>
  );
}
