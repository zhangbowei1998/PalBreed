import type { AgentData, PalProfile } from "../types";

const baseUrl = import.meta.env.VITE_AGENT_SERVICE_BASE_URL ?? "http://localhost:9000";
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const AGENT_TIMEOUT_MS = 15000;
const API_TIMEOUT_MS = 8000;

const TOKEN_KEY = "pl_agent_token";

type Envelope<T> = {
  success: boolean;
  data: T;
};

// ── token 管理（登录注册 UI 上线后由登录页写入） ──

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), AGENT_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(init.headers ?? {}),
      },
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") {
      throw new Error("请求超时：agent-service 无响应，请稍后重试");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const text = await res.text();
    if (res.status === 409 && text.includes("尚未确认目标帕鲁")) {
      throw new Error("会话已失效（服务可能重启），请重新发送一次查询");
    }
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

export type AuthResult = {
  token: string;
  user: { id: string; username: string; created_at: string };
};

export async function register(username: string, password: string): Promise<AuthResult> {
  const data = await request<AuthResult>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(data.token);
  return data;
}

export async function login(username: string, password: string): Promise<AuthResult> {
  const data = await request<AuthResult>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(data.token);
  return data;
}

export async function fetchCurrentUser(): Promise<AuthResult["user"] | null> {
  if (!getToken()) return null;
  try {
    const data = await request<{ user: AuthResult["user"] }>("/auth/me", { method: "GET" });
    return data.user;
  } catch {
    setToken(null);
    return null;
  }
}

export function logout(): void {
  setToken(null);
}

export async function getPalProfile(palId: string): Promise<PalProfile> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${apiBaseUrl}/api/pal/${encodeURIComponent(palId)}`, {
      signal: controller.signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") {
      throw new Error("请求超时：API 无响应");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  const body = (await res.json()) as Envelope<PalProfile>;
  return body.data;
}

/** 按中文名/英文名/ID/别名解析帕鲁 profile（含图片），供内联头像展示。 */
export async function resolvePalByName(name: string): Promise<PalProfile | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${apiBaseUrl}/api/pal/resolve/${encodeURIComponent(name)}`, {
      signal: controller.signal,
    });
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) return null;
  try {
    const body = (await res.json()) as Envelope<PalProfile>;
    return body.data ?? null;
  } catch {
    return null;
  }
}
