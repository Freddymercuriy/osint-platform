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

export async function handle<T>(res: Response): Promise<T> {
  // Token muddati tugagan/yaroqsiz — tizimdan chiqarib, login sahifasiga qaytaramiz
  if (res.status === 401 && typeof window !== "undefined" && getToken()) {
    clearToken();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.assign("/login?expired=1");
    }
    throw new Error("Sessiya muddati tugadi. Qaytadan kiring.");
  }
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
  detail: string | null;
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

async function postSearch(path: string, query: string): Promise<SearchResponse> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ query }),
  });
  return handle<SearchResponse>(res);
}

export const searchUsername = (query: string) => postSearch("/api/search/username", query);
export const searchEmail = (query: string) => postSearch("/api/search/email", query);
export const searchPhone = (query: string) => postSearch("/api/search/phone", query);

export async function getHistory(): Promise<SearchJob[]> {
  const res = await fetch(`${API_URL}/api/search/history`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<SearchJob[]>(res);
}

// --- Telegram (foydalanuvchi akkaunti) ---
export type TgStatus = {
  configured: boolean;
  session: boolean;
  authorized: boolean;
  account: string | null;
  chats_filter: string[];
  uz_filter: boolean;
  message: string;
};

export async function getTgStatus(): Promise<TgStatus> {
  const res = await fetch(`${API_URL}/api/telegram/status`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<TgStatus>(res);
}

// --- Events (yangiliklar/tadbirlar) ---
export type EventItem = {
  source: string;
  title: string;
  url: string;
  summary: string;
  published: string | null;
  lang: string;
  category: string;
  id?: number;
  first_seen?: string | null;
};

export type EventsResponse = { count: number; items: EventItem[] };

export type CollectorStatus = {
  enabled: boolean;
  running: boolean;
  poll_seconds: number;
  last_run: string | null;
  last_duration: number | null;
  last_new: number;
  last_error: string | null;
  runs: number;
  total_events: number;
  by_category: Record<string, number>;
  notify_telegram: boolean;
  notify_categories: string[];
  notified_total: number;
};

// --- Saytdagi ogohlantirishlar (🔔) ---
export type NotificationItem = EventItem & { id: number; first_seen: string; is_new: boolean };

export type NotificationsResponse = {
  unread: number;
  categories: string[];
  seen_at: string | null;
  items: NotificationItem[];
};

export async function getNotifications(limit = 20): Promise<NotificationsResponse> {
  const res = await fetch(`${API_URL}/api/notifications?limit=${limit}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<NotificationsResponse>(res);
}

export async function markNotificationsRead(): Promise<void> {
  const res = await fetch(`${API_URL}/api/notifications/read`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  await handle(res);
}

export async function getCollectorStatus(): Promise<CollectorStatus> {
  const res = await fetch(`${API_URL}/api/events/status`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<CollectorStatus>(res);
}

export async function refreshEvents(): Promise<{ new: number }> {
  const res = await fetch(`${API_URL}/api/events/refresh`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<{ new: number }>(res);
}

export async function getEvents(
  q?: string,
  category?: string,
  limit = 60,
  offset?: number,
): Promise<EventsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (q) params.set("q", q);
  if (category) params.set("category", category);
  if (offset) params.set("offset", String(offset));
  const res = await fetch(`${API_URL}/api/events?${params.toString()}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<EventsResponse>(res);
}
