"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import FilterBar from "@/components/FilterBar";
import { DASHBOARDS } from "@/lib/nav";
import type { FilterOptions, FilterState } from "@/lib/types";

interface Props {
  options: FilterOptions | null;
  filters: FilterState;
  onFiltersChange: (next: FilterState) => void;
}

export default function Sidebar({ options, filters, onFiltersChange }: Props) {
  const path = usePathname();

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-slate-200 bg-slate-100">
      <div className="border-b border-slate-200 bg-red-700 px-5 py-4">
        <p className="text-lg font-semibold tracking-tight text-white">
          Manipal
        </p>
        <p className="text-xs text-red-100">Pharmacy &amp; Inventory Analytics</p>
      </div>

      <nav className="space-y-0.5 p-3">
        <Link href="/"
              className={`block rounded-md px-3 py-2 text-sm ${
                path === "/"
                  ? "bg-sky-50 font-medium text-sky-700"
                  : "text-slate-600 hover:bg-slate-50"}`}>
          Overview
        </Link>

        {DASHBOARDS.map((d) => (
          <Link key={d.slug} href={`/${d.slug}`}
                className={`block rounded-md px-3 py-2 text-sm ${
                  path === `/${d.slug}`
                    ? "bg-sky-50 font-medium text-sky-700"
                    : "text-slate-600 hover:bg-slate-50"}`}>
            {d.title}
          </Link>
        ))}
      </nav>

      {/* Scope and Filters - one panel for the whole app, below the nav
          links, instead of a bar repeated at the top of every page. */}
      <div className="flex-1 overflow-y-auto border-t border-slate-200 p-3">
        <FilterBar options={options} value={filters} onChange={onFiltersChange} />
      </div>

      <div className="border-t border-slate-200 px-5 py-3">
        <p className="text-[11px] leading-tight text-slate-400">
          Demo environment &middot; synthetic data
          <br />
          Jan 2025 &ndash; Dec 2026
        </p>
      </div>
    </aside>
  );
}