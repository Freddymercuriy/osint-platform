/**
 * Admin API mijozi (backend `/api/admin/*`, `/api/telegram/*`, hodisa kategoriyasini qo'lda o'zgartirish, fasetlar).
 * Barcha so'rovlar `apiFetch` orqali (Accept-Language) va `handle` (kodli xato → ApiError).
 */
import { apiFetch, getToken, handle, invalidateMe, type EventItem } from "@/lib/api";

import { API_URL } from "@/lib/config";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Authorization: `Bearer ${getToken()}` };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await apiFetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(res);
}

const qs = (o: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

/* ------------------------------------------------------------------ manbalar */
export type SourceStatus = "ok" | "degraded" | "down" | "blocked" | "auth_missing" | "disabled" | "never_run";
export const SOURCE_STATUSES: SourceStatus[] = ["ok", "degraded", "down", "blocked", "auth_missing", "disabled", "never_run"];

export type SourceInput = {
  name: string;
  kind: string;
  config: Record<string, unknown>;
  lang: string;
  category: string | null;
  scope: "regional" | "global";
  region_filter: boolean;
  cyber_filter: boolean;
  translate: boolean;
  enabled: boolean;
  interval_seconds: number;
  jitter_pct: number;
  backfill_days: number;
  api_key_env: string | null;
  notes: string;
};

export type Source = SourceInput & {
  id: number;
  status: SourceStatus;
  key_configured: boolean | null;
  next_run_at: string | null;
  last_check_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  last_http_status: number | null;
  last_latency_ms: number | null;
  consecutive_failures: number;
  last_items: number | null;
  last_new_items: number | null;
  newest_item_at: string | null;
  down_since: string | null;
  /** Oxirgi urinish natijasi (ok / blocked / rate_limited / error ...) */
  last_outcome: string | null;
  /** Oxirgi xatoda sayt so'ragan kutish, soniya (Retry-After / FloodWait) */
  retry_after_seconds: number | null;
  baseline_done: boolean;
  items_24h: number;
  uptime_7d: number | null;
  created_at: string;
  updated_at: string;
};

export type SourceRun = {
  id: number;
  started_at: string;
  duration_ms: number | null;
  http_status: number | null;
  ok: boolean;
  outcome: string;
  items: number;
  new_items: number;
  error: string | null;
  manual: boolean;
  retry_after_seconds: number | null;
  /** Shu urinishdan keyin keyingisigacha rejalashtirilgan kutish, soniya */
  wait_seconds: number | null;
};

export type SourceTest = {
  ok: boolean;
  outcome: string;
  http_status: number | null;
  latency_ms: number;
  items: number;
  passed: number;
  samples: { title: string; url: string; published: string | null; matched_keywords: string[] }[];
  error: string | null;
  note: string | null;
  retry_after_seconds: number | null;
};

export type SourceRunNow = {
  ok: boolean;
  outcome: string;
  status: SourceStatus;
  http_status: number | null;
  duration_ms: number;
  items: number;
  passed: number;
  new: number;
  merged: number;
  error: string | null;
  next_run_at: string | null;
  retry_after_seconds: number | null;
  wait_seconds: number | null;
};

export type ConnectorInfo = {
  kind: string;
  title: string;
  config_fields: string[];
  key: "required" | "optional" | null;
  default_key_env: string | null;
};

export type SourcesExport = { format: string; version: number; exported_at: string; sources: SourceInput[] };

export const listSources = (f: { status?: string; kind?: string; enabled?: boolean } = {}) =>
  request<Source[]>("GET", `/api/admin/sources${qs(f)}`);
export const getSource = (id: number) => request<Source>("GET", `/api/admin/sources/${id}`);
export const createSource = (data: SourceInput) => request<Source>("POST", "/api/admin/sources", data);
export const updateSource = (id: number, data: Partial<SourceInput>) =>
  request<Source>("PATCH", `/api/admin/sources/${id}`, data);
export const deleteSource = (id: number) => request<void>("DELETE", `/api/admin/sources/${id}`);
export const enableSource = (id: number) => request<Source>("POST", `/api/admin/sources/${id}/enable`);
export const disableSource = (id: number) => request<Source>("POST", `/api/admin/sources/${id}/disable`);
export const testSource = (id: number) => request<SourceTest>("POST", `/api/admin/sources/${id}/test`);
export const testSourceDraft = (data: SourceInput) => request<SourceTest>("POST", "/api/admin/sources/test", data);
export const runSource = (id: number) => request<SourceRunNow>("POST", `/api/admin/sources/${id}/run`);
export const sourceRuns = (id: number, limit = 50) =>
  request<SourceRun[]>("GET", `/api/admin/sources/${id}/runs${qs({ limit })}`);
export const exportSources = () => request<SourcesExport>("GET", "/api/admin/sources/export");
export const importSources = (sources: SourceInput[]) =>
  request<{ created: number; updated: number }>("POST", "/api/admin/sources/import", { sources });
export const listConnectors = () => request<ConnectorInfo[]>("GET", "/api/admin/connectors");

export type CollectorAdmin = {
  enabled: boolean;
  running: boolean;
  lock_held: boolean;
  started_at: string | null;
  last_tick: string | null;
  active: number[];
  runs: number;
  last_error: string | null;
  sources_total: number;
  sources_enabled: number;
  by_status: Record<string, number>;
  runs_24h: number;
  failed_runs_24h: number;
};
export const getCollectorAdmin = () => request<CollectorAdmin>("GET", "/api/admin/collector");

/* ------------------------------------------------------------------ kategoriyalar */
export type CategoryRules = {
  stems?: Record<string, string[]>;
  patterns?: string[];
  exclude?: string[];
  weight?: number;
  min_score?: number;
};

export type CategoryInput = {
  slug: string;
  name_en: string;
  name_ru: string;
  name_uz: string;
  description_en: string;
  description_ru: string;
  description_uz: string;
  severity: "info" | "low" | "medium" | "high" | "critical";
  color: string;
  icon: string;
  notify: boolean;
  retention_days: number | null;
  sort_order: number;
  enabled: boolean;
  rules: CategoryRules;
};

export type CategoryAdmin = CategoryInput & {
  id: number;
  is_system: boolean;
  event_count: number;
  created_at: string;
  updated_at: string;
};

export type ReclassifyResult = {
  dry_run: boolean;
  considered: number;
  changed: number;
  severity_changed: number;
  locked_skipped: number;
  transitions: Record<string, number>;
  samples: { id: number; title: string; from: string; to: string }[];
};

export const listAdminCategories = () => request<CategoryAdmin[]>("GET", "/api/admin/categories");
export const createCategory = (data: CategoryInput) => request<CategoryAdmin>("POST", "/api/admin/categories", data);
export const updateCategory = (id: number, data: Partial<Omit<CategoryInput, "slug">>) =>
  request<CategoryAdmin>("PATCH", `/api/admin/categories/${id}`, data);
export const deleteCategory = (id: number) =>
  request<{ moved_to_other: number }>("DELETE", `/api/admin/categories/${id}`);
export const reorderCategories = (ids: number[]) =>
  request<CategoryAdmin[]>("POST", "/api/admin/categories/reorder", { ids });
export const reclassify = (dryRun: boolean) =>
  request<ReclassifyResult>("POST", `/api/admin/categories/reclassify${qs({ dry_run: dryRun })}`);

/* ------------------------------------------------------------------ foydalanuvchilar */
export type AdminUserRow = {
  id: number;
  email: string;
  role: "admin" | "analyst";
  is_active: boolean;
  locale: string | null;
  created_at: string;
  searches: number;
};
export const listUsers = () => request<AdminUserRow[]>("GET", "/api/admin/users");
export const updateUser = async (id: number, data: { role?: "admin" | "analyst"; is_active?: boolean }) => {
  const r = await request<AdminUserRow>("PATCH", `/api/admin/users/${id}`, data);
  invalidateMe();
  return r;
};

/* ------------------------------------------------------------------ tarjima */
export type TranslationStatus = {
  provider: string;
  configured: boolean;
  enabled: boolean;
  month: string;
  chars_used: number;
  requests: number;
  char_limit: number; // 0 — chegarasiz
  remaining: number;
  budget_exhausted: boolean;
  key_rejected: boolean;
  paused_until: string | null;
  last_run: string | null;
  last_error: string | null;
  counts: Record<string, Record<string, number>>;
  cache_entries: number;
  failed: { event_id: number; lang: string; attempts: number; error: string | null }[];
};
export const getTranslationStatus = () => request<TranslationStatus>("GET", "/api/admin/translations");
export const retryFailedTranslations = () =>
  request<{ requeued: number }>("POST", "/api/admin/translations/retry-failed");
export const runTranslations = () => request<Record<string, unknown>>("POST", "/api/admin/translations/run");

/* ------------------------------------------------------------------ Telegram */
export type TgChat = {
  id: number; title: string; username: string | null; kind: string;
  archived: boolean;
  /** bu chat uchun telegram_user manbasi allaqachon bor */
  monitored: boolean;
};
/** Akkauntdagi barcha kanal/guruhlar (5 daq. keshlanadi; `refresh` — qayta o'qish) */
export const getTgChats = (refresh = false) =>
  request<TgChat[]>("GET", `/api/telegram/chats${refresh ? "?refresh=true" : ""}`);

/* ------------------------------------------------------------------ hodisalar */
export const setEventCategory = (id: number, category: string) =>
  request<EventItem>("PATCH", `/api/events/${id}`, { category });

export type FacetItem = { value: string; label: string | null; count: number };
export type EventFacets = {
  sources: FacetItem[];
  countries: FacetItem[];
  source_langs: FacetItem[];
  channels: FacetItem[];
  severities: FacetItem[];
  scopes: FacetItem[];
};
export const getEventFacets = () => request<EventFacets>("GET", "/api/events/facets");
