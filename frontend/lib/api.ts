const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "osint_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

type ApiError = { detail?: string };

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `Xatolik: ${res.status}`;
    try {
      const data = (await res.json()) as ApiError;
      if (data.detail) msg = data.detail;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export async function register(email: string, password: string) {
  const res = await fetch(`${API_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handle(res);
}

export async function login(email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const data = await handle<{ access_token: string }>(res);
  setToken(data.access_token);
  return data.access_token;
}

export type Me = { id: number; email: string; is_active: boolean; created_at: string };

export async function getMe(): Promise<Me> {
  const res = await fetch(`${API_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<Me>(res);
}

function authHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${getToken()}`,
  };
}

// --- OSINT qidiruv ---
export type CollectResult = {
  source: string;
  type: string;
  value: string;
  url: string | null;
  status: "found" | "not_found" | "error";
  confidence: number;
};

export type SearchResponse = {
  job_id: number;
  query: string;
  kind: string;
  checked: number;
  found: number;
  results: CollectResult[];
};

export type SearchJob = {
  id: number;
  kind: string;
  query: string;
  status: string;
  created_at: string;
};

export async function searchUsername(query: string): Promise<SearchResponse> {
  const res = await fetch(`${API_URL}/api/search/username`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ query }),
  });
  return handle<SearchResponse>(res);
}

export async function getHistory(): Promise<SearchJob[]> {
  const res = await fetch(`${API_URL}/api/search/history`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<SearchJob[]>(res);
}
