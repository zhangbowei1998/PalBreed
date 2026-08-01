import { useEffect, useMemo, useRef } from "react";

import type { AgentAction, ChatMessage, PalProfile } from "../types";

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
  const listRef = useRef<HTMLDivElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  const messageCount = useMemo(() => messages.length, [messages]);

  useEffect(() => {
    const host = listRef.current;
    const end = endRef.current;
    if (!host || !end) return;
    const id = requestAnimationFrame(() => {
      end.scrollIntoView({ behavior: "smooth", block: "end" });
    });
    return () => cancelAnimationFrame(id);
  }, [messageCount, loading]);

  return (
    <div className="message-list" ref={listRef}>
      {messages.map((msg) => (
        <article key={msg.id} className={`message message-${msg.role}`}>
          <header>{msg.role === "user" ? "你" : "Agent"}</header>
          {msg.role === "assistant"
            ? renderAssistantContent(msg.content, palNameToId, palProfiles, loading, pairActionMap, onSelectPair)
            : <p>{msg.content}</p>}
        </article>
      ))}
      {loading && (
        <article className="message message-assistant message-loading">
          <header>Agent</header>
          <p>正在分析并查询中...</p>
        </article>
      )}
      <div ref={endRef} />
    </div>
  );
}
