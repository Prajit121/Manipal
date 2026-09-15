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

// Stacked for the sidebar rather than a row - the network hierarchy (Region/
// Zone/Cluster) is scoped to two units for this presentation, so only Unit
// is shown; see app/config.py: ACTIVE_UNITS to restore the rest later.
export default function FilterBar({ options, value, onChange }: Props) {
  const units = options?.units ?? [];
  const set = (patch: Partial<FilterState>) => onChange({ ...value, ...patch });

  const cls =
    "w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm " +
    "text-slate-700 focus:border-sky-500 focus:outline-none";
  const label = "block text-[11px] font-semibold uppercase tracking-wide text-slate-400 mb-1";

  const isFiltered =
    value.unit !== "All" || value.department !== "All" ||
    value.stock_take_group !== "All";

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          Scope
        </p>
        <label className={label}>Unit</label>
        <select className={cls} value={value.unit}
                onChange={(e) => set({ unit: e.target.value })}>
          <option value="All">All Units</option>
          {units.map((u) => (
            <option key={u.Unit_ID} value={u.Unit_ID}>
              {u.Unit_Name} ({u.Unit_ID})
            </option>
          ))}
        </select>
        <p className="mt-2 inline-block rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
          Viewing: {scopeLabel(value, options)}
        </p>
      </div>

      <div className="space-y-3 border-t border-slate-100 pt-3">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          Filters
        </p>
        <div>
          <label className={label}>Department</label>
          <select className={cls} value={value.department}
                  onChange={(e) => set({ department: e.target.value })}>
            <option value="All">All Departments</option>
            {options?.departments.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label className={label}>Stock Take Group</label>
          <select className={cls} value={value.stock_take_group}
                  onChange={(e) => set({ stock_take_group: e.target.value })}>
            <option value="All">All Groups</option>
            {options?.stock_take_groups.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
        <div>
          <label className={label}>Period</label>
          <select className={cls} value={value.preset}
                  onChange={(e) => set({ preset: e.target.value })}>
            {options?.presets.map((p) => (
              <option key={p} value={p}>{PRESET_LABELS[p] ?? p}</option>
            ))}
          </select>
        </div>
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