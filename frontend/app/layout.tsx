"use client";

import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { fetchFilterOptions } from "@/lib/api";
import { FilterProvider } from "@/lib/filter-context";
import type { FilterOptions, FilterState } from "@/lib/types";
import "./globals.css";


export const DEFAULT_FILTERS: FilterState = {
  region: "All", zone: "All", cluster: "All", unit: "All",
  department: "All", stock_take_group: "All", preset: "full_range",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [options, setOptions] = useState<FilterOptions | null>(null);
  // One filter state for the whole app - lives here, not per-page, so it
  // survives navigation between dashboards instead of resetting every time.
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);

  useEffect(() => {
    fetchFilterOptions().then(setOptions).catch(() => {});
  }, []);

  return (
    <html lang="en">
      <body className="antialiased">
        <div className="flex h-screen overflow-hidden bg-slate-50">
          <Sidebar options={options} filters={filters} onFiltersChange={setFilters} />
          <main className="flex-1 overflow-y-auto overflow-x-hidden p-6">
            {/* Pages read filters via a tiny context rather than fetching
                their own - see lib/filter-context.tsx. */}
            <FilterProvider value={{ filters, options }}>
              {children}
            </FilterProvider>
          </main>
        </div>
      </body>
    </html>
  );
}