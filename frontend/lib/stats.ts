import { getToken, type EventItem } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type DayBucket = { day: string; total: number; by_category: Record<string, number> };

export type Overview = {
  total_events: number;
  new_24h: number;
  by_category: Record<string, number>;
  daily: DayBucket[];
  top_sources: { source: string; count: number }[];
  critical: (EventItem & { id: number; first_seen: string })[];
  searches_total: number;
  searches_by_kind: Record<string, number>;
};

export async function getOverview(days = 14): Promise<Overview> {
  const res = await fetch(`${API_URL}/api/stats/overview?days=${days}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error(`Statistika yuklanmadi (${res.status})`);
  return res.json();
}
