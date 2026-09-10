import type { Kpi } from "@/lib/types";

// Red is reserved for risk flags only - never decorative. That rule holds
// across all five dashboards.
const TONE: Record<string, string> = {
  neutral: "text-slate-900",
  positive: "text-emerald-700",
  risk: "text-red-600",
};

export default function KpiCard({ kpi }: { kpi: Kpi }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {kpi.label}
      </p>
      <p className={`mt-2 text-2xl font-semibold ${TONE[kpi.tone]}`}>
        {kpi.display}
      </p>
      {kpi.delta_pct !== null && (
        <p className={`mt-1 text-xs ${kpi.delta_pct >= 0 ? "text-emerald-600" : "text-red-600"}`}>
          {kpi.delta_pct >= 0 ? "up" : "down"} {Math.abs(kpi.delta_pct).toFixed(1)}%
        </p>
      )}
    </div>
  );
}
