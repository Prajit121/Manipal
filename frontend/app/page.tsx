"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchDashboard, scopeLabel } from "@/lib/api";
import { useFilters } from "@/lib/filter-context";
import { DASHBOARDS } from "@/lib/nav";
import type { DashboardResponse } from "@/lib/types";

export default function OverviewPage() {
  const { filters, options } = useFilters();
  const [data, setData] = useState<Record<string, DashboardResponse>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all(
      DASHBOARDS.map((d) =>
        fetchDashboard(d.slug, filters)
          .then((r) => [d.slug, r] as const)
          .catch(() => null)),
    ).then((results) => {
      const next: Record<string, DashboardResponse> = {};
      results.forEach((r) => { if (r) next[r[0]] = r[1]; });
      setData(next);
      setLoading(false);
    });
  }, [filters]);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Overview</h1>
        <p className="text-sm text-slate-500">
          All dashboards at a glance{" "}
          <span className="text-slate-400">&middot;</span>{" "}
          <span className="font-medium text-slate-600">
            {scopeLabel(filters, options)}
          </span>
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {DASHBOARDS.map((d) => {
          const res = data[d.slug];
          const kpi = res?.kpis.find((k) => k.label === d.headlineKpi)
                      ?? res?.kpis[0];
          return (
            <Link key={d.slug} href={`/${d.slug}`}
                  className="group rounded-lg border border-slate-200 bg-white p-5
                             transition hover:border-sky-300 hover:shadow-sm">
              <p className="text-sm font-medium text-slate-900 group-hover:text-sky-700">
                {d.title}
              </p>
              <p className="mt-1 text-xs leading-snug text-slate-500">
                {d.subtitle}
              </p>

              {loading ? (
                <div className="mt-4 h-8 w-32 animate-pulse rounded bg-slate-200" />
              ) : kpi ? (
                <>
                  <p className={`mt-4 text-2xl font-semibold ${
                    kpi.tone === "risk" ? "text-red-600" : "text-slate-900"}`}>
                    {kpi.display}
                  </p>
                  <p className="text-[11px] uppercase tracking-wide text-slate-400">
                    {kpi.label}
                  </p>
                </>
              ) : (
                <p className="mt-4 text-sm text-slate-400">No data</p>
              )}

              {res?.insights?.[0] && (
                <p className="mt-3 border-t border-slate-100 pt-3 text-xs
                              leading-snug text-slate-500">
                  {res.insights[0]}
                </p>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
