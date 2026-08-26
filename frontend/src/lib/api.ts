const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  org?: string,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (org) headers["X-Organization-ID"] = org;
  if (typeof document !== "undefined" && !["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith("review_csrf="))
      ?.split("=")
      .slice(1)
      .join("=");
    if (csrf) headers["X-CSRF-Token"] = decodeURIComponent(csrf);
  }
  if (body instanceof FormData) {
    /* browser sets multipart boundary */
  } else if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: "include",
    body:
      body instanceof FormData
        ? body
        : body === undefined
          ? undefined
          : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "请求失败");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  auth: {
    register: (body: RegisterInput) =>
      request<AuthResponse>("POST", "/api/auth/register", body),
    login: (body: { email: string; password: string; remember_me: boolean }) =>
      request<AuthResponse>("POST", "/api/auth/login", body),
    verify: (token: string) =>
      request<{ status: string }>("POST", "/api/auth/verify-email", { token }),
    resend: (email: string) =>
      request<{ status: string }>("POST", "/api/auth/resend-verification", {
        email,
      }),
    forgot: (email: string) =>
      request<{ status: string }>("POST", "/api/auth/forgot-password", {
        email,
      }),
    reset: (token: string, password: string) =>
      request<{ status: string }>("POST", "/api/auth/reset-password", {
        token,
        password,
      }),
    me: () => request<UserProfile>("GET", "/api/auth/me"),
    refresh: () => request<AuthResponse>("POST", "/api/auth/refresh"),
    logout: () => request<{ status: string }>("POST", "/api/auth/logout"),
  },
  reviews: {
    list: (organizationId: string) =>
      request<ReviewSummary[]>(
        "GET",
        `/api/reviews?organization_id=${encodeURIComponent(organizationId)}`,
      ),
    create: (body: {
      organization_id: string;
      topic?: string;
      max_round: number;
    }) =>
      request<ReviewSummary>(
        "POST",
        "/api/reviews",
        body,
        body.organization_id,
      ),
    get: (id: string, org?: string) =>
      request<ReviewDetail>("GET", `/api/reviews/${id}`, undefined, org),
    upload: (id: string, file: File, org?: string) => {
      const form = new FormData();
      form.append("file", file);
      return request<ReviewDocument>(
        "POST",
        `/api/reviews/${id}/documents`,
        form,
        org,
      );
    },
    start: (id: string, org?: string) =>
      request<ReviewProgress>(
        "POST",
        `/api/reviews/${id}/start`,
        undefined,
        org,
      ),
    humanReview: (id: string, approved: boolean, note?: string, org?: string) =>
      request<ReviewProgress>(
        "POST",
        `/api/reviews/${id}/human-review`,
        { approved, note },
        org,
      ),
    evidence: (id: string, org?: string) =>
      request<EvidenceItem[]>(
        "GET",
        `/api/reviews/${id}/evidence`,
        undefined,
        org,
      ),
    report: (id: string, org?: string) =>
      request<{ markdown: string }>(
        "GET",
        `/api/reviews/${id}/report`,
        undefined,
        org,
      ),
    downloadUrl: (id: string) => `${BASE}/api/reviews/${id}/report.md`,
    delete: (id: string, org?: string) =>
      request<void>("DELETE", `/api/reviews/${id}`, undefined, org),
  },
  organizations: {
    invite: (id: string, email: string) =>
      request("POST", `/api/organizations/${id}/invites`, { email }),
    removeMember: (id: string, userId: string) =>
      request<void>("DELETE", `/api/organizations/${id}/members/${userId}`),
  },
};

export function authToken() {
  return null;
}
export function apiBase() {
  return BASE;
}
export interface RegisterInput {
  email: string;
  password: string;
  display_name?: string;
  organization_name?: string;
  invite_token?: string;
}
export interface Organization {
  id: string;
  name: string;
  role: string;
}
export interface UserProfile {
  id: string;
  email: string;
  display_name: string | null;
  email_verified: boolean;
  organizations: Organization[];
  created_at: string;
}
export interface AuthResponse {
  access_token?: string;
  refresh_token?: string;
  user: UserProfile;
  token_type: string;
}
export interface ReviewSummary {
  id: string;
  organization_id: string;
  topic: string | null;
  max_round: number;
  current_round: number;
  current_stage: string;
  status: string;
  document_count: number;
  evidence_count: number;
  creator_id: string;
  creator_name: string | null;
  created_at: string;
  updated_at: string;
}
export interface ReviewDocument {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  parse_status: string;
  parse_error?: string | null;
}
export interface ReviewOutput {
  id: string;
  agent_role: string;
  round_num: number;
  sequence: number;
  content_markdown: string;
  structured_data?: Record<string, unknown> | null;
  created_at: string;
}
export interface ReviewDetail extends ReviewSummary {
  documents: ReviewDocument[];
  outputs: ReviewOutput[];
  report_markdown?: string | null;
  error_message?: string | null;
}
export interface ReviewProgress {
  session_id: string;
  status: string;
  current_stage: string;
  current_round: number;
  max_round: number;
  output_count: number;
  evidence_count: number;
  report_ready: boolean;
  error_message?: string | null;
}
export interface EvidenceItem {
  id: string;
  round_num: number;
  argument_role: string;
  claim_text: string;
  verdict: "verified" | "contradicted" | "uncertain";
  rationale: string;
  sources: {
    id: string;
    title: string;
    url: string;
    snippet?: string | null;
  }[];
}
