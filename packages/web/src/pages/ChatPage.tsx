import { App, Avatar, Button, Dropdown, Space } from "antd";
import type { MenuProps } from "antd";
import { UserOutlined, LogoutOutlined, LoginOutlined } from "@ant-design/icons";
import { useState } from "react";
import { ActionTray } from "../components/ActionTray";
import { AuthModal } from "../components/AuthModal";
import { BreedingTree, type SelectedPair } from "../components/BreedingTree";
import { ChatComposer } from "../components/ChatComposer";
import { MessageList } from "../components/MessageList";
import { useAgentSession } from "../hooks/useAgentSession";
import { useAuth } from "../hooks/useAuth";
import type { AgentAction } from "../types";

export function ChatPage() {
  const { user, login, register, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const userKey = user?.id ?? "anonymous";

  const {
    messages,
    actions,
    palProfiles,
    stateSnapshot,
    loading,
    error,
    sendMessage,
    runAction,
  } = useAgentSession(userKey);

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

  const userMenu: MenuProps = {
    items: [
      { key: "logout", icon: <LogoutOutlined />, label: "退出登录" },
    ],
    onClick: ({ key }) => {
      if (key === "logout") {
        logout();
      }
    },
  };

  return (
    <App className="app-root">
      <main className="layout">
        <header className="topbar">
          <div className="brand">
            <span className="brand-emoji" aria-hidden="true">🦤</span>
            <div className="brand-text">
              <h1>帕鲁AI助手</h1>
              <p>AI 会思考、调用配种工具，再给你精确答案。</p>
            </div>
          </div>
          <div className="topbar-user">
            {user ? (
              <Dropdown menu={userMenu} placement="bottomRight">
                <Button type="text" className="user-chip">
                  <Space>
                    <Avatar size={26} style={{ background: "#111111" }}>{user.username.slice(0, 1).toUpperCase()}</Avatar>
                    <span>{user.username}</span>
                  </Space>
                </Button>
              </Dropdown>
            ) : (
              <Button type="primary" icon={<LoginOutlined />} onClick={() => setAuthOpen(true)}>
                登录 / 注册
              </Button>
            )}
          </div>
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

        <AuthModal
          open={authOpen}
          onClose={() => setAuthOpen(false)}
          onLogin={login}
          onRegister={register}
        />
      </main>
    </App>
  );
}
