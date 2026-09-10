"use client";

import { useMemo } from "react";
import { scopeLabel } from "@/lib/api";
import type { FilterOptions, FilterState } from "@/lib/types";

const PRESET_LABELS: Record<string, string> = {
  this_month: "This Month",
  this_quarter: "This Quarter",
  ytd: "YTD",
  "2025": "2025",
  "2026": "2026",
  full_range: "Full Range",
};

interface Props {
  options: FilterOptions | null;
  value: FilterState;
  onChange: (next: FilterState) => void;
}

export default function FilterBar({ options, value, onChange }: Props) {
  const units = options?.units ?? [];

  // Cascading: each level only offers children of what is selected above it.
  // Picking a level clears everything below, so you can never end up with an
  // impossible combination like Region=North + Unit=H001.
  const zones = useMemo(() => {
    const pool = value.region === "All"
      ? units : units.filter((u) => u.Region === value.region);
    return [...new Set(pool.map((u) => u.Zone))].sort();
  }, [units, value.region]);

  const clusters = useMemo(() => {
    let pool = units;
    if (value.region !== "All") pool = pool.filter((u) => u.Region === value.region);
    if (value.zone !== "All") pool = pool.filter((u) => u.Zone === value.zone);
    return [...new Set(pool.map((u) => u.Cluster))].sort();
  }, [units, value.region, value.zone]);

  const unitList = useMemo(() => {
    let pool = units;
    if (value.region !== "All") pool = pool.filter((u) => u.Region === value.region);
    if (value.zone !== "All") pool = pool.filter((u) => u.Zone === value.zone);
    if (value.cluster !== "All") pool = pool.filter((u) => u.Cluster === value.cluster);
    return pool;
  }, [units, value.region, value.zone, value.cluster]);

  const set = (patch: Partial<FilterState>) => onChange({ ...value, ...patch });

  const cls =
    "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm " +
    "text-slate-700 focus:border-sky-500 focus:outline-none";

  const isFiltered =
    value.region !== "All" || value.zone !== "All" || value.cluster !== "All" ||
    value.unit !== "All" || value.department !== "All" ||
    value.stock_take_group !== "All";

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Scope
        </span>

        <select className={cls} value={value.region}
                onChange={(e) => set({ region: e.target.value, zone: "All",
                                       cluster: "All", unit: "All" })}>
          <option value="All">All Regions</option>
          {options?.regions.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>

        <select className={cls} value={value.zone}
                onChange={(e) => set({ zone: e.target.value, cluster: "All", unit: "All" })}>
          <option value="All">All Zones</option>
          {zones.map((z) => <option key={z} value={z}>{z}</option>)}
        </select>

        <select className={cls} value={value.cluster}
                onChange={(e) => set({ cluster: e.target.value, unit: "All" })}>
          <option value="All">All Clusters</option>
          {clusters.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        <select className={cls} value={value.unit}
                onChange={(e) => set({ unit: e.target.value })}>
          <option value="All">All Units</option>
          {unitList.map((u) => (
            <option key={u.Unit_ID} value={u.Unit_ID}>
              {u.Unit_Name} ({u.Unit_ID})
            </option>
          ))}
        </select>

        <span className="ml-auto rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          Viewing: {scopeLabel(value, options)}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Filters
        </span>

        <select className={cls} value={value.department}
                onChange={(e) => set({ department: e.target.value })}>
          <option value="All">All Departments</option>
          {options?.departments.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>

        <select className={cls} value={value.stock_take_group}
                onChange={(e) => set({ stock_take_group: e.target.value })}>
          <option value="All">All Groups</option>
          {options?.stock_take_groups.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>

        <select className={cls} value={value.preset}
                onChange={(e) => set({ preset: e.target.value })}>
          {options?.presets.map((p) => (
            <option key={p} value={p}>{PRESET_LABELS[p] ?? p}</option>
          ))}
        </select>

        {isFiltered && (
          <button className="text-xs text-sky-600 underline"
                  onClick={() => onChange({
                    region: "All", zone: "All", cluster: "All", unit: "All",
                    department: "All", stock_take_group: "All",
                    preset: value.preset,
                  })}>
            Clear all
          </button>
        )}
      </div>
    </div>
  );
}
