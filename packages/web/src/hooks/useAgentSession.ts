import { useEffect, useRef, useState } from "react";
import { action, chatStream, getPalProfile, resolvePalByName } from "../services/agentClient";
import type { AgentAction, AgentData, AgentTraceInfo, ChatMessage, PalProfile } from "../types";

/** 会话 ID 按用户维度存储，避免不同用户共用 localStorage key 造成串扰。 */
function sessionStorageKey(userKey: string): string {
  return `pl_agent_session_id_${userKey}`;
}

function makeSessionId(): string {
  return `web-${Math.random().toString(36).slice(2, 10)}`;
}

/** 会话 ID 持久化到 localStorage：页面刷新 / 服务重启后同一浏览器保持同一会话。 */
function getOrCreateSessionId(userKey: string): string {
  const key = sessionStorageKey(userKey);
  const existing = localStorage.getItem(key);
  if (existing) {
    return existing;
  }
  const fresh = makeSessionId();
  localStorage.setItem(key, fresh);
  return fresh;
}

function extractTrace(data: AgentData): AgentTraceInfo | null {
  const trace = data.meta?.trace;
  if (!trace || typeof trace !== "object") return null;
  return trace as AgentTraceInfo;
}

function normalizeMessages(data: AgentData, baseId: string): ChatMessage[] {
  const trace = extractTrace(data);
  return data.messages.map((m, idx) => ({
    id: `${baseId}-${idx}`,
    role: m.role,
    content: m.content,
    trace: m.role === "assistant" ? trace : null,
  }));
}

export function useAgentSession(userKey: string) {
  const [sessionId, setSessionId] = useState(() => getOrCreateSessionId(userKey));
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [stateSnapshot, setStateSnapshot] = useState<AgentData["state_snapshot"] | null>(null);
  const [palProfiles, setPalProfiles] = useState<Record<string, PalProfile>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const userKeyRef = useRef(userKey);

  // 用户切换（登录/登出）时：会话、消息、动作全部重置，防止记忆串扰。
  useEffect(() => {
    if (userKeyRef.current === userKey) return;
    userKeyRef.current = userKey;
    setSessionId(getOrCreateSessionId(userKey));
    setMessages([]);
    setActions([]);
    setStateSnapshot(null);
    setPalProfiles({});
    setError(null);
  }, [userKey]);

  async function prefetchPalProfiles(snapshot: AgentData["state_snapshot"] | null) {
    if (!snapshot) return;
    const ids = new Set<string>();
    for (const edge of snapshot.edges ?? []) {
      ids.add(edge.parent_a_id);
      ids.add(edge.parent_b_id);
      ids.add(edge.child_pal_id);
    }
    for (const c of snapshot.target_candidates ?? []) {
      ids.add(c.pal_id);
    }

    const missing = [...ids].filter((id) => !(id in palProfiles));
    if (missing.length === 0) return;

    const entries = await Promise.all(
      missing.map(async (id) => {
        try {
          const profile = await getPalProfile(id);
          return [id, profile] as const;
        } catch {
          return null;
        }
      }),
    );

    const next: Record<string, PalProfile> = {};
    for (const item of entries) {
      if (!item) continue;
      next[item[0]] = item[1];
    }
    if (Object.keys(next).length > 0) {
      setPalProfiles((prev) => ({ ...prev, ...next }));
    }
  }

  /** 从回复文本提取 **帕鲁名**，加载其 profile 用于内联头像展示。 */
  async function prefetchPalProfilesFromText(texts: string[]) {
    const names = new Set<string>();
    for (const text of texts) {
      const matches = text.match(/\*\*([^*]+)\*\*/g) ?? [];
      for (const m of matches) {
        const name = m.replace(/\*\*/g, "").trim();
        // 去掉可能附带的标点/编号前缀后缀
        const clean = name.replace(/^[·\-*.\s]+/, "").replace(/[：:。，,）)\]　\s]+$/, "");
        if (clean) names.add(clean);
      }
    }
    if (names.size === 0) return;

    // 已在 palProfiles 中的（按 cn_name/en_name/id 命中）跳过
    const known = new Set<string>();
    for (const p of Object.values(palProfiles)) {
      known.add(p.cn_name);
      known.add(p.en_name);
      known.add(p.id);
    }
    const missing = [...names].filter((n) => !known.has(n));
    if (missing.length === 0) return;

    const entries = await Promise.all(
      missing.map(async (name) => {
        try {
          const profile = await resolvePalByName(name);
          return profile ? [profile.id, profile] as const : null;
        } catch {
          return null;
        }
      }),
    );

    const next: Record<string, PalProfile> = {};
    for (const item of entries) {
      if (!item) continue;
      next[item[0]] = item[1];
    }
    if (Object.keys(next).length > 0) {
      setPalProfiles((prev) => ({ ...prev, ...next }));
    }
  }

  async function sendMessage(input: string) {
    if (!input.trim()) return;
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: input,
    };
    const assistantId = `a-${Date.now()}`;

    setError(null);
    setLoading(true);
    setMessages((prev) => [...prev, userMsg]);
    // 先占位一条空的 assistant 消息，流式过程中持续填充
    setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "" }]);

    try {
      const doneBox: { data: AgentData | null } = { data: null };
      await chatStream(
        sessionId,
        input,
        (delta) => {
          // 累积文本到当前 assistant 消息
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + delta } : m,
            ),
          );
        },
        (data) => {
          doneBox.data = data;
        },
      );

      const doneData = doneBox.data;
      if (doneData) {
        // 流式完成：第一条消息（LLM 文本）替换占位并补 trace；
        // 其余 extra 消息（如确定性的父母候选行）追加到列表，
        // 保证配种方案可点击、配种树可展开。
        const finalMsgs = normalizeMessages(doneData, `a-${Date.now()}`);
        setMessages((prev) => {
          const rest = prev.filter((m) => m.id !== assistantId);
          const head = finalMsgs[0]
            ? [{ ...finalMsgs[0], id: assistantId }]
            : [];
          return [...rest, ...head, ...finalMsgs.slice(1)];
        });
        setActions(doneData.actions);
        setStateSnapshot(doneData.state_snapshot);
        void prefetchPalProfiles(doneData.state_snapshot);
        void prefetchPalProfilesFromText(doneData.messages.map((m) => m.content));
      }
    } catch (err) {
      setError((err as Error).message);
      // 出错时移除空的占位消息，避免留下空白气泡
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
    } finally {
      setLoading(false);
    }
  }

  async function runAction(item: AgentAction): Promise<AgentData | null> {
    setError(null);
    setLoading(true);

    const payload = { ...item.payload };
    if (item.action === "expand_parent" && !payload.source_message_id) {
      payload.source_message_id = `web-msg-${Date.now()}`;
    }

    try {
      const data = await action(sessionId, item.action, payload);
      setMessages((prev) => [...prev, ...normalizeMessages(data, `a-${Date.now()}`)]);
      setActions(data.actions);
      setStateSnapshot(data.state_snapshot);
      void prefetchPalProfiles(data.state_snapshot);
      void prefetchPalProfilesFromText(data.messages.map((m) => m.content));
      return data;
    } catch (err) {
      setError((err as Error).message);
      return null;
    } finally {
      setLoading(false);
    }
  }

  return {
    sessionId,
    messages,
    actions,
    palProfiles,
    stateSnapshot,
    loading,
    error,
    sendMessage,
    runAction,
  };
}
