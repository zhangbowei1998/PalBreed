import { ActionTray } from "../components/ActionTray";
import { ChatComposer } from "../components/ChatComposer";
import { MessageList } from "../components/MessageList";
import { StatePanel } from "../components/StatePanel";
import { useAgentSession } from "../hooks/useAgentSession";

export function ChatPage() {
  const {
    sessionId,
    messages,
    actions,
    stateSnapshot,
    graphJson,
    loading,
    error,
    canSummarize,
    sendMessage,
    runAction,
    summarize,
  } = useAgentSession();

  return (
    <main className="layout">
      <section className="chat-shell">
        <header className="hero">
          <h1>配种探索控制台</h1>
          <p>可点击父节点扩展，并在任意时刻生成已探索路线。</p>
        </header>

        {error && <div className="error">{error}</div>}

        <MessageList messages={messages} />
        <ActionTray
          actions={actions}
          loading={loading}
          onAction={runAction}
          onSummarize={summarize}
          canSummarize={canSummarize}
        />
        <ChatComposer loading={loading} onSend={sendMessage} />
      </section>

      <StatePanel sessionId={sessionId} stateSnapshot={stateSnapshot} graphJson={graphJson} />
    </main>
  );
}
