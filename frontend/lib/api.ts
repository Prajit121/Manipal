import type { DashboardResponse, FilterOptions, FilterState } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

/** Turn filter state into the query string every endpoint accepts. */
export function toQuery(f: FilterState): string {
  return new URLSearchParams({
    region: f.region,
    zone: f.zone,
    cluster: f.cluster,
    unit: f.unit,
    department: f.department,
    stock_take_group: f.stock_take_group,
    preset: f.preset,
  }).toString();
}

/** The scope the user is currently looking at - deepest selection wins. */
export function scopeLabel(f: FilterState, options: FilterOptions | null): string {
  if (f.unit !== "All") {
    const u = options?.units.find((x) => x.Unit_ID === f.unit);
    return u ? `${u.Unit_Name} (${u.Unit_ID})` : f.unit;
  }
  if (f.cluster !== "All") return f.cluster;
  if (f.zone !== "All") return f.zone;
  if (f.region !== "All") return f.region;
  return "Network";
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export function fetchFilterOptions(): Promise<FilterOptions> {
  return get<FilterOptions>("/api/filter-options");
}

/** One function for all dashboards - they share the envelope. */
export function fetchDashboard(
  slug: string,
  filters: FilterState,
): Promise<DashboardResponse> {
  return get<DashboardResponse>(`/api/${slug}?${toQuery(filters)}`);
}
