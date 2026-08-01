import { useMemo, useState } from "react";
import { action, chat } from "../services/agentClient";
import type { AgentAction, AgentData, ChatMessage } from "../types";

function makeSessionId(): string {
  return `web-${Math.random().toString(36).slice(2, 10)}`;
}

function normalizeMessages(data: AgentData, baseId: string): ChatMessage[] {
  return data.messages.map((m, idx) => ({
    id: `${baseId}-${idx}`,
    role: m.role,
    content: m.content,
  }));
}

export function useAgentSession() {
  const [sessionId] = useState(() => makeSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [stateSnapshot, setStateSnapshot] = useState<AgentData["state_snapshot"] | null>(null);
  const [graphJson, setGraphJson] = useState<AgentData["graph_json"] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSummarize = useMemo(
    () => actions.some((a) => a.action === "summarize_route"),
    [actions],
  );

  async function sendMessage(input: string) {
    if (!input.trim()) return;
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: input,
    };

    setError(null);
    setLoading(true);
    setMessages((prev) => [...prev, userMsg]);

    try {
      const data = await chat(sessionId, input);
      setMessages((prev) => [...prev, ...normalizeMessages(data, `a-${Date.now()}`)]);
      setActions(data.actions);
      setStateSnapshot(data.state_snapshot);
      setGraphJson(data.graph_json ?? null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function runAction(item: AgentAction) {
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
      setGraphJson(data.graph_json ?? null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function summarize() {
    const summarizeAction = actions.find((a) => a.action === "summarize_route") ?? {
      action: "summarize_route" as const,
      label: "生成配种路线",
      payload: { mode: "explored_only" },
    };
    await runAction(summarizeAction);
  }

  return {
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
  };
}
