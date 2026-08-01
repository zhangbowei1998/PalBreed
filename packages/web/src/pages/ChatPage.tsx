import { ActionTray } from "../components/ActionTray";
import { BreedingTree, type SelectedPair } from "../components/BreedingTree";
import { ChatComposer } from "../components/ChatComposer";
import { MessageList } from "../components/MessageList";
import { useAgentSession } from "../hooks/useAgentSession";
import type { AgentAction } from "../types";

export function ChatPage() {
  const {
    messages,
    actions,
    palProfiles,
    stateSnapshot,
    loading,
    error,
    sendMessage,
    runAction,
  } = useAgentSession();

  const palNameToId = Object.fromEntries(
    (stateSnapshot?.edges ?? []).flatMap((edge) => [
      [edge.parent_a_name, edge.parent_a_id],
      [edge.parent_b_name, edge.parent_b_id],
    ]),
  ) as Record<string, string>;

  const displayActions = actions.filter(
    (item) =>
      item.action !== "expand_parent"
      && item.action !== "select_parent_pair"
      && item.action !== "continue_from_parent",
  );

  const pairActionMap: Record<string, AgentAction> = Object.fromEntries(
    actions
      .filter((item) => item.action === "select_parent_pair")
      .map((item) => {
        const childPalId = String(item.payload.child_pal_id ?? "");
        const pairIndex = Number(item.payload.pair_index);
        return [`${childPalId}:${pairIndex}`, item] as const;
      }),
  );

  const selectedPairs: SelectedPair[] = (stateSnapshot?.selected_pairs ?? []) as SelectedPair[];

  async function handleSelectPair(action: AgentAction) {
    const selected = await runAction(action);
    if (!selected) return;

    const continueActions = selected.actions.filter(
      (item) => item.action === "continue_from_parent",
    );
    for (const continueAction of continueActions) {
      const done = await runAction(continueAction);
      if (!done) break;
    }
  }

  return (
    <main className="layout">
      <section className="chat-shell">
        <header className="hero">
          <h1>配种探索控制台</h1>
          <p>点击父母组合即可展开配种二叉树，实时查看每一步的配种路径。</p>
        </header>

        {error && <div className="error">{error}</div>}

        <BreedingTree
          targetPal={stateSnapshot?.target_pal ?? null}
          selectedPairs={selectedPairs}
          palNameToId={palNameToId}
          palProfiles={palProfiles}
        />

        <MessageList
          messages={messages}
          palNameToId={palNameToId}
          palProfiles={palProfiles}
          loading={loading}
          pairActionMap={pairActionMap}
          onSelectPair={handleSelectPair}
        />
        <ActionTray
          actions={displayActions}
          loading={loading}
          onAction={async (item) => {
            await runAction(item);
          }}
        />
        <ChatComposer loading={loading} onSend={sendMessage} />
      </section>
    </main>
  );
}
