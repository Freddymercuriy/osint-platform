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
  meCache = null;
}

// --- Til: cookie (next-intl o'qiydi) va backend'ga Accept-Language ---
const LOCALE_COOKIE = "NEXT_LOCALE";

export function currentLocale(): string {
  if (typeof document === "undefined") return "uz";
  const m = document.cookie.match(/(?:^|;\s*)NEXT_LOCALE=(uz|ru|en)/);
  return m ? m[1] : document.documentElement.lang || "uz";
}

export function setLocaleCookie(locale: string) {
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
}

/** Backend'ga har so'rovda interfeys tili yuboriladi — xato matnlari shu tilda qaytadi. */
export function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!headers.has("Accept-Language")) headers.set("Accept-Language", currentLocale());
  return fetch(input, { ...init, headers });
}

/** Backend xatosi: `detail` (tarjima qilingan matn) va barqaror `code`. */
export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type ErrorBody = { detail?: string | { msg?: string }[]; code?: string };

export async function handle<T>(res: Response): Promise<T> {
  // Token muddati tugagan/yaroqsiz — tizimdan chiqarib, login sahifasiga qaytaramiz
  if (res.status === 401 && typeof window !== "undefined" && getToken()) {
    clearToken();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.assign("/login?expired=1");
    }
    throw new ApiError("session_expired", 401, "session_expired");
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    let code: string | undefined;
    try {
      const data = (await res.json()) as ErrorBody;
      code = data.code;
      if (typeof data.detail === "string") msg = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]?.msg) msg = data.detail[0].msg;
    } catch {
      /* ignore */
    }
    throw new ApiError(msg, res.status, code);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function updateMyLocale(locale: string): Promise<Me> {
  const res = await apiFetch(`${API_URL}/api/auth/me`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ locale }),
  });
  meCache = null;
  return handle<Me>(res);
}

export async function register(email: string, password: string) {
  const res = await apiFetch(`${API_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handle(res);
}

export async function login(email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password });
  const res = await apiFetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const data = await handle<{ access_token: string }>(res);
  setToken(data.access_token);
  return data.access_token;
}

export type Role = "admin" | "analyst";

export type Me = {
  id: number;
  email: string;
  is_active: boolean;
  role: Role;
  locale: string | null;
  created_at: string;
};

// Bitta sahifa yuklanishida /me bir marta so'raladi (layout, dashboard, events bir xil javobni ishlatadi)
let meCache: { token: string | null; promise: Promise<Me> } | null = null;

export async function getMe(): Promise<Me> {
  const token = getToken();
  if (meCache && meCache.token === token) return meCache.promise;
  const promise = apiFetch(`${API_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((res) => handle<Me>(res));
  meCache = { token, promise };
  promise.catch(() => {
    meCache = null;
  });
  return promise;
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
  created_at?: string | null;
  results: CollectResult[];
};

export type SearchJob = {
  id: number;
  kind: string;
  query: string;
  status: string;
  created_at: string;
  /** tekshirilgan manbalar soni */
  checked: number;
  /** topilganlar soni */
  found: number;
};

async function postSearch(path: string, query: string): Promise<SearchResponse> {
  const res = await apiFetch(`${API_URL}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ query }),
  });
  return handle<SearchResponse>(res);
}

export const searchUsername = (query: string) => postSearch("/api/search/username", query);
export const searchEmail = (query: string) => postSearch("/api/search/email", query);
export const searchPhone = (query: string) => postSearch("/api/search/phone", query);
export const searchDomain = (query: string) => postSearch("/api/search/domain", query);

export type HistoryParams = { kind?: string; q?: string; limit?: number; offset?: number };

/** Qidiruv tarixi (yangi → eski). `kind`/`q` bo'yicha filtr, `limit`/`offset` bilan sahifalash. */
export async function getHistory(params: HistoryParams = {}): Promise<SearchJob[]> {
  const sp = new URLSearchParams();
  if (params.kind) sp.set("kind", params.kind);
  if (params.q) sp.set("q", params.q);
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  const qs = sp.toString();
  const res = await apiFetch(`${API_URL}/api/search/history${qs ? `?${qs}` : ""}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<SearchJob[]>(res);
}

/** Bitta qidiruvning saqlangan natijalari. */
export async function getJob(id: number): Promise<SearchResponse> {
  const res = await apiFetch(`${API_URL}/api/search/jobs/${id}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<SearchResponse>(res);
}

/** Eksport qilinadigan hisobot (backend: `JobReport`). */
export type JobReport = {
  report: { platform: string; format_version: number; generated_at: string; notice: string };
  job: { id: number; kind: string; query: string; status: string; created_at: string };
  summary: { checked: number; found: number; not_found: number; error: number };
  results: CollectResult[];
};

/** Bitta qidiruvning hisoboti (JSON eksport va chop etish sahifasi uchun). */
export async function getJobReport(id: number): Promise<JobReport> {
  const res = await apiFetch(`${API_URL}/api/search/jobs/${id}/export`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<JobReport>(res);
}

export async function deleteJob(id: number): Promise<void> {
  const res = await apiFetch(`${API_URL}/api/search/jobs/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) await handle(res); // 204 — tanasiz
}

/** Tarixni tozalash (kind berilsa — faqat shu modul). O'chirilganlar sonini qaytaradi. */
export async function clearHistory(kind?: string): Promise<{ deleted: number }> {
  const res = await apiFetch(`${API_URL}/api/search/history${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<{ deleted: number }>(res);
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
  const res = await apiFetch(`${API_URL}/api/telegram/status`, {
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
  // v2
  source_id?: number | null;
  category_id?: number | null;
  channel?: string;
  scope?: string;
  severity?: string;
  countries?: string[];
  sector?: string | null;
  actor?: string | null;
  matched_keywords?: string[];
  extra?: Record<string, unknown>;
  also_reported_by?: { source: string; url: string; at: string }[];
  is_baseline?: boolean;
  // tarjima (?lang=)
  source_lang?: string | null;
  display_lang?: string | null;
  translated?: boolean;
  translation_status?: string | null;
  original_title?: string | null;
  original_summary?: string | null;
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
  /** lenta boshlanish sanasi (undan oldingi hodisalar saqlanmaydi) */
  since: string | null;
  /** 0 = eski hodisalar o'chirilmaydi */
  retention_days: number;
  /** muddatidan qat'i nazar saqlanadigan kategoriyalar */
  retention_keep: string[];
  last_purged: number;
  purged_total: number;
};

// --- Saytdagi ogohlantirishlar (🔔) ---
export type NotificationItem = EventItem & { id: number; first_seen: string; is_new: boolean };

export type NotificationsResponse = {
  unread: number;
  categories: string[];
  seen_at: string | null;
  items: NotificationItem[];
};

export async function getNotifications(limit = 20, lang?: string): Promise<NotificationsResponse> {
  const res = await apiFetch(`${API_URL}/api/notifications?limit=${limit}${lang ? `&lang=${lang}` : ""}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<NotificationsResponse>(res);
}

export async function markNotificationsRead(): Promise<void> {
  const res = await apiFetch(`${API_URL}/api/notifications/read`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  await handle(res);
}

export async function getCollectorStatus(): Promise<CollectorStatus> {
  const res = await apiFetch(`${API_URL}/api/events/status`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<CollectorStatus>(res);
}

export async function refreshEvents(): Promise<{ new: number }> {
  const res = await apiFetch(`${API_URL}/api/events/refresh`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<{ new: number }>(res);
}

/** Hodisalar filtrlari (hammasi birlashadi; ro'yxatlar — YOKI). URL query bilan bir xil nomlar. */
export type EventFilters = {
  q?: string;
  category?: string[];
  severity?: string[];
  country?: string[];
  channel?: string[];
  source?: string[];
  scope?: "regional" | "global" | "all";
  source_lang?: string[];
  date_from?: string;
  date_to?: string;
};

export function eventFiltersToParams(f: EventFilters, params = new URLSearchParams()): URLSearchParams {
  for (const [k, v] of Object.entries(f)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) {
      if (v.length) params.set(k, v.join(","));
    } else params.set(k, String(v));
  }
  return params;
}

/**
 * Hodisalar. v1 chaqiruvi `getEvents(q, category, limit, offset)` ham ishlaydi;
 * yangi: `getEvents({filters, lang, limit, offset})` — `lang` berilsa matn shu tilda (zanjir: til → en → asl).
 */
export async function getEvents(
  arg?: string | { filters?: EventFilters; lang?: string; limit?: number; offset?: number },
  category?: string,
  limit = 60,
  offset?: number,
): Promise<EventsResponse> {
  const opts =
    typeof arg === "object" && arg !== null
      ? arg
      : { filters: { q: arg || undefined, category: category ? [category] : undefined }, limit, offset };
  const params = eventFiltersToParams(opts.filters ?? {});
  params.set("limit", String(opts.limit ?? 60));
  if (opts.offset) params.set("offset", String(opts.offset));
  if (opts.lang) params.set("lang", opts.lang);
  const res = await apiFetch(`${API_URL}/api/events?${params.toString()}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<EventsResponse>(res);
}

export type AuthConfig = { registration_open: boolean };

export async function getAuthConfig(): Promise<AuthConfig> {
  return handle<AuthConfig>(await apiFetch(`${API_URL}/api/auth/config`));
}


// --- Kategoriyalar (bazadan) ---
export type Category = {
  id: number;
  slug: string;
  name_en: string;
  name_ru: string;
  name_uz: string;
  description_en: string;
  description_ru: string;
  description_uz: string;
  severity: string;
  color: string;
  icon: string;
  notify: boolean;
  retention_days: number | null;
  sort_order: number;
  enabled: boolean;
  is_system: boolean;
  event_count: number;
};

export async function getCategories(): Promise<Category[]> {
  const res = await apiFetch(`${API_URL}/api/categories`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<Category[]>(res);
}
