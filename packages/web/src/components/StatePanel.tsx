type Props = {
  sessionId: string;
  stateSnapshot: unknown;
  graphJson: unknown;
};

export function StatePanel({ sessionId, stateSnapshot, graphJson }: Props) {
  return (
    <aside className="state-panel">
      <h3>会话状态</h3>
      <p>session: {sessionId}</p>
      <pre>{JSON.stringify(stateSnapshot, null, 2)}</pre>
      <h3>路线图数据</h3>
      <pre>{JSON.stringify(graphJson, null, 2)}</pre>
    </aside>
  );
}
