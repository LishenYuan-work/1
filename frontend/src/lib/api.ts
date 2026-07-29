/** API 客户端 — 封装对后端的所有请求 */

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ====== Auth ======
export const auth = {
  register: (data: { username: string; password: string; display_name?: string }) =>
    request<AuthResponse>("POST", "/api/auth/register", data),
  login: (data: { username: string; password: string }) =>
    request<AuthResponse>("POST", "/api/auth/login", data),
  me: () => request<UserProfile>("GET", "/api/auth/me"),
};

// ====== Debates ======
export const debates = {
  create: (data: CreateDebateInput) =>
    request<DebateSummary>("POST", "/api/debates", data),
  list: (params?: { status?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    return request<DebateSummary[]>("GET", `/api/debates?${qs}`);
  },
  myList: () => request<DebateSummary[]>("GET", "/api/debates/my"),
  get: (id: string) => request<DebateDetail>("GET", `/api/debates/${id}`),
  delete: (id: string) => request<void>("DELETE", `/api/debates/${id}`),
  followup: (id: string, data: { message_index: number; question: string }) =>
    request<{ reply: string; agent: string }>("POST", `/api/debates/${id}/followup`, data),
  streamUrl: (id: string) => `${BASE}/api/debates/${id}/stream`,
  live: (id: string) => request<LiveState>("GET", `/api/debates/${id}/live`),
};

// ====== Comments ======
export const comments = {
  list: (debateId: string) => request<CommentItem[]>("GET", `/api/debates/${debateId}/comments`),
  create: (debateId: string, data: { content: string; parent_id?: number }) =>
    request<CommentItem>("POST", `/api/debates/${debateId}/comments`, data),
  delete: (debateId: string, commentId: number) =>
    request<void>("DELETE", `/api/debates/${debateId}/comments/${commentId}`),
};

// ====== Templates ======
export const templates = {
  list: () => request<Template[]>("GET", "/api/templates"),
  recommend: (topic: string) =>
    request<{ agents: AgentConfig[] }>("POST", "/api/templates/ai-recommend", { topic }),
};

// ====== Types ======
export interface AgentConfig {
  name: string;
  role: string;
  stance: string;
}

export interface CreateDebateInput {
  topic: string;
  agents: AgentConfig[];
  rounds: number;
  mode?: string;
  visibility?: string;
}

export interface DebateSummary {
  id: string;
  topic: string;
  rounds: number;
  status: string;
  mode: string;
  visibility: string;
  agents: AgentConfig[];
  message_count: number;
  creator_name: string | null;
  created_at: string;
}

export interface DebateDetail extends DebateSummary {
  messages: MessageItem[];
  error_message: string | null;
  completed_at: string | null;
}

export interface MessageItem {
  agent_name: string;
  content: string;
  round_num: number;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserProfile;
}

export interface UserProfile {
  id: string;
  username: string;
  display_name: string | null;
  email: string | null;
  created_at: string;
}

export interface CommentItem {
  id: number;
  debate_id: string;
  user_id: string | null;
  username: string | null;
  content: string;
  parent_id: number | null;
  replies: CommentItem[];
  created_at: string;
}

export interface Template {
  name: string;
  agents: AgentConfig[];
}

/** SSE 事件类型 */
export interface LiveState {
  status: string;
  messages: MessageItem[];
  streaming: { agent_name: string; round_num: number; text: string } | null;
}

export type SSEEvent =
  | { type: "round_start"; round: number; total: number }
  | { type: "agent_start"; agent: string; round: number }
  | { type: "chunk"; agent: string; round: number; text: string }
  | { type: "agent_end"; agent: string; round: number; full_text: string }
  | { type: "round_end"; round: number }
  | { type: "done"; debate_id?: string; status?: string }
  | { type: "error"; message: string; agent?: string }
  | { type: "cancelled"; message?: string };
