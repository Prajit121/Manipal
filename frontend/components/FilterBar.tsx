"use client";

import { scopeLabel } from "@/lib/api";
import type { FilterOptions, FilterState } from "@/lib/types";

const PRESET_LABELS: Record<string, string> = {
  this_month: "This Month",
  this_quarter: "This Quarter",
  ytd: "FY YTD",
  fy2025: "FY2025",
  fy2026: "FY2026",
  full_range: "Full Range",
};

interface Props {
  options: FilterOptions | null;
  value: FilterState;
  onChange: (next: FilterState) => void;
}

// The network hierarchy (Region/Zone/Cluster) is scoped to two units for this
// presentation - Pune and Goa share one Region and each sits alone in its own
// Zone/Cluster, so those three dropdowns would offer nothing a plain Unit
// selector doesn't already. Removed rather than shown half-broken. The
// backend and data still carry the full 12-unit hierarchy (app/config.py:
// ACTIVE_UNITS) - restoring the other three dropdowns is switching that list
// back, not rebuilding this component.
export default function FilterBar({ options, value, onChange }: Props) {
  const units = options?.units ?? [];
  const set = (patch: Partial<FilterState>) => onChange({ ...value, ...patch });

  const cls =
    "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm " +
    "text-slate-700 focus:border-sky-500 focus:outline-none";

  const isFiltered =
    value.unit !== "All" || value.department !== "All" ||
    value.stock_take_group !== "All";

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Scope
        </span>

        <select className={cls} value={value.unit}
                onChange={(e) => set({ unit: e.target.value })}>
          <option value="All">All Units</option>
          {units.map((u) => (
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
                    ...value, unit: "All", department: "All",
                    stock_take_group: "All",
                  })}>
            Clear all
          </button>
        )}
      </div>
    </div>
  );
}