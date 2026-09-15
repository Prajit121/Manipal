"use client";

import { createContext, useContext } from "react";
import type { FilterOptions, FilterState } from "@/lib/types";

interface FilterContextValue {
  filters: FilterState;
  options: FilterOptions | null;
}

const FilterContext = createContext<FilterContextValue | null>(null);

export function FilterProvider({
  value, children,
}: { value: FilterContextValue; children: React.ReactNode }) {
  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

/** Every dashboard page calls this instead of holding its own filter state. */
export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error("useFilters must be used inside FilterProvider");
  return ctx;
}