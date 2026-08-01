import type { AgentAction } from "../types";

type Props = {
  actions: AgentAction[];
  loading: boolean;
  onAction: (action: AgentAction) => Promise<void>;
};

export function ActionTray({ actions, loading, onAction }: Props) {
  return (
    <section className="action-tray">
      {actions.length > 0 && (
        <div className="action-row">
          {actions.map((item, idx) => (
            <button key={`${item.action}-${idx}`} onClick={() => onAction(item)} disabled={loading}>
              {item.label}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
