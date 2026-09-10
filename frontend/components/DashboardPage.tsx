"use client";

import { useEffect, useState } from "react";
import ChartPanel from "@/components/ChartPanel";
import DataTable from "@/components/DataTable";
import FilterBar from "@/components/FilterBar";
import InsightCallout from "@/components/InsightCallout";
import KpiCard from "@/components/KpiCard";
import { fetchDashboard, fetchFilterOptions, scopeLabel } from "@/lib/api";
import type { DashboardResponse, FilterOptions, FilterState } from "@/lib/types";

const DEFAULT_FILTERS: FilterState = {
  region: "All",
  zone: "All",
  cluster: "All",
  unit: "All",
  department: "All",
  stock_take_group: "All",
  preset: "full_range",
};

interface Props {
  slug: string;      // API path and route, from lib/nav.ts
  title: string;
  subtitle: string;
}

// Every dashboard renders through this one component. That only works because
// all five endpoints return the identical envelope - the contract locked in
// schemas.py is what makes the frontend this small.
export default function DashboardPage({ slug, title, subtitle }: Props) {
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFilterOptions().then(setOptions).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchDashboard(slug, filters)
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [slug, filters]);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        <p className="text-sm text-slate-500">
          {subtitle} <span className="text-slate-400">&middot;</span>{" "}
          <span className="font-medium text-slate-600">
            {scopeLabel(filters, options)}
          </span>
        </p>
      </header>

      <FilterBar options={options} value={filters} onChange={setFilters} />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Could not reach the API. Is the backend running on port 8000?
        </div>
      )}

      {loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-lg bg-slate-200" />
            ))}
          </div>
          <div className="h-72 animate-pulse rounded-lg bg-slate-200" />
        </div>
      )}

      {!loading && data && data.row_count === 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-10 text-center">
          <p className="text-slate-600">No data for the selected filters.</p>
          <button className="mt-3 text-sm text-sky-600 underline"
                  onClick={() => setFilters(DEFAULT_FILTERS)}>
            Reset filters
          </button>
        </div>
      )}

      {!loading && data && data.row_count > 0 && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            {data.kpis.map((k) => <KpiCard key={k.label} kpi={k} />)}
          </div>

          <InsightCallout insights={data.insights} />

          <div className="grid gap-4 lg:grid-cols-2">
            {data.charts.map((c) => <ChartPanel key={c.id} spec={c} />)}
          </div>

          <DataTable table={data.table} />
        </>
      )}
    </div>
  );
}
