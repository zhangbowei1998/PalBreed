import type { AgentData } from "../types";

const baseUrl = import.meta.env.VITE_AGENT_SERVICE_BASE_URL ?? "http://localhost:9000";

type Envelope<T> = {
  success: boolean;
  data: T;
};

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  const body = (await res.json()) as Envelope<T>;
  return body.data;
}

export async function chat(sessionId: string, message: string): Promise<AgentData> {
  return request<AgentData>("/agent/chat", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, message }),
  });
}

export async function action(
  sessionId: string,
  actionName: string,
  payload: Record<string, unknown>,
): Promise<AgentData> {
  return request<AgentData>("/agent/action", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, action: actionName, ...payload }),
  });
}

export async function getSession(sessionId: string): Promise<{ state_snapshot: AgentData["state_snapshot"] }> {
  return request<{ state_snapshot: AgentData["state_snapshot"] }>(`/agent/session/${sessionId}`, {
    method: "GET",
  });
}
