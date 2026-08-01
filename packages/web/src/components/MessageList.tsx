import { Avatar } from "antd";
import { Bubble, type BubbleItemType } from "@ant-design/x";
import { RobotOutlined, UserOutlined } from "@ant-design/icons";
import type { AgentAction, ChatMessage, PalProfile } from "../types";
import { ThinkingProcess } from "./ThinkingProcess";

type Props = {
  messages: ChatMessage[];
  palNameToId: Record<string, string>;
  palProfiles: Record<string, PalProfile>;
  loading: boolean;
  pairActionMap: Record<string, AgentAction>;
  onSelectPair: (action: AgentAction) => Promise<void>;
};

function renderAssistantContent(
  content: string,
  palNameToId: Record<string, string>,
  palProfiles: Record<string, PalProfile>,
  loading: boolean,
  pairActionMap: Record<string, AgentAction>,
  onSelectPair: (action: AgentAction) => Promise<void>,
) {
  const lines = content.split("\n");
  let currentChildPal: string | null = null;
  return (
    <div className="message-body">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        const pairMatch = trimmed.match(/^(?:([0-9]+)\.|-)\s*(.+?)\s*\+\s*(.+?)\s*\((.+)\)$/);
        const parentHeaderMatch = trimmed.match(/^(.+?)\s+的父母候选：$/);
        if (parentHeaderMatch) {
          const rawName = parentHeaderMatch[1].trim();
          currentChildPal = rawName;
          const profile = palProfiles[rawName];
          const displayName = profile?.cn_name ?? rawName;
          return (
            <p key={idx}>
              {displayName} 的父母候选：
            </p>
          );
        }
        if (!pairMatch) {
          return (
            <p key={idx}>
              {line}
            </p>
          );
        }

        const pairNumber = pairMatch[1] ? Number(pairMatch[1]) : null;
        const parentA = pairMatch[2].trim();
        const parentB = pairMatch[3].trim();
        const method = pairMatch[4].trim();
        const idA = palNameToId[parentA];
        const idB = palNameToId[parentB];
        const profileA = idA ? palProfiles[idA] : undefined;
        const profileB = idB ? palProfiles[idB] : undefined;
        const labelA = profileA?.cn_name ?? parentA;
        const labelB = profileB?.cn_name ?? parentB;
        const pairIndex = pairNumber ? pairNumber - 1 : null;
        const pairKey = currentChildPal && pairIndex !== null
          ? `${currentChildPal}:${pairIndex}`
          : null;
        const pairAction = pairKey ? pairActionMap[pairKey] : undefined;
        const clickable = Boolean(pairAction);

        return (
          <p key={idx} className="pair-line">
            {clickable ? (
              <span
                className={`pair-select-btn${loading ? " disabled" : ""}`}
                role="button"
                tabIndex={0}
                onClick={() => {
                  if (loading || !pairAction) return;
                  void onSelectPair(pairAction);
                }}
                onKeyDown={(event) => {
                  if (loading || !pairAction) return;
                  if (event.key !== "Enter" && event.key !== " ") return;
                  event.preventDefault();
                  void onSelectPair(pairAction);
                }}
                title="点击选择这组父母"
              >
                <span>{pairNumber ? `${pairNumber}.` : "-"}</span>
                <span className="pal-inline-btn" role="presentation">
                  {profileA?.image_url ? (
                    <img className="pal-inline-avatar" src={profileA.image_url} alt="" aria-hidden="true" />
                  ) : (
                    <span className="pal-inline-avatar pal-inline-avatar-fallback">{labelA.slice(0, 1)}</span>
                  )}
                  <span>{labelA}</span>
                </span>
                <span> + </span>
                <span className="pal-inline-btn" role="presentation">
                  {profileB?.image_url ? (
                    <img className="pal-inline-avatar" src={profileB.image_url} alt="" aria-hidden="true" />
                  ) : (
                    <span className="pal-inline-avatar pal-inline-avatar-fallback">{labelB.slice(0, 1)}</span>
                  )}
                  <span>{labelB}</span>
                </span>
                <span className="pair-method"> ({method})</span>
              </span>
            ) : (
              <>
                <span>{pairNumber ? `${pairNumber}.` : "-"}</span>
                <span className="pal-inline-btn" role="presentation">
                  {profileA?.image_url ? (
                    <img className="pal-inline-avatar" src={profileA.image_url} alt="" aria-hidden="true" />
                  ) : (
                    <span className="pal-inline-avatar pal-inline-avatar-fallback">{labelA.slice(0, 1)}</span>
                  )}
                  <span>{labelA}</span>
                </span>
                <span> + </span>
                <span className="pal-inline-btn" role="presentation">
                  {profileB?.image_url ? (
                    <img className="pal-inline-avatar" src={profileB.image_url} alt="" aria-hidden="true" />
                  ) : (
                    <span className="pal-inline-avatar pal-inline-avatar-fallback">{labelB.slice(0, 1)}</span>
                  )}
                  <span>{labelB}</span>
                </span>
                <span className="pair-method"> ({method})</span>
              </>
            )}
          </p>
        );
      })}
    </div>
  );
}

export function MessageList({ messages, palNameToId, palProfiles, loading, pairActionMap, onSelectPair }: Props) {
  const items: BubbleItemType[] = [
    ...messages.map((msg) => {
      if (msg.role === "user") {
        return {
          key: msg.id,
          role: "user" as const,
          content: msg.content,
        };
      }
      return {
        key: msg.id,
        role: "assistant" as const,
        content: (
          <div>
            {msg.trace && <ThinkingProcess trace={msg.trace} />}
            {renderAssistantContent(
              msg.content,
              palNameToId,
              palProfiles,
              loading,
              pairActionMap,
              onSelectPair,
            )}
          </div>
        ),
      };
    }),
    ...(loading
      ? [{
          key: "typing",
          role: "assistant" as const,
          content: (
            <div className="typing">
              <span />
              <span />
              <span />
            </div>
          ),
        }]
      : []),
  ];

  return (
    <Bubble.List
      className="bubble-list"
      items={items}
      autoScroll
      role={{
        user: {
          placement: "end",
          variant: "filled",
          avatar: <Avatar size={28} icon={<UserOutlined />} />,
        },
        assistant: {
          placement: "start",
          variant: "outlined",
          avatar: <Avatar size={28} style={{ background: "#111111" }} icon={<RobotOutlined />} />,
        },
      }}
    />
  );
}
