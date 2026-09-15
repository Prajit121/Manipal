"use client";

import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { inrCompact } from "@/lib/format";
import type { Chart as ChartSpec } from "@/lib/types";

// One accent ramp. Red is NOT in here - it is reserved for risk flags only.
const COLORS = ["#0284c7", "#0d9488", "#7c3aed", "#c2410c", "#4f46e5",
                "#0891b2", "#65a30d", "#9333ea", "#0369a1", "#15803d"];

const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Merge multi-series data onto a shared x axis so Recharts can plot it. */
function mergeSeries(spec: ChartSpec) {
  const byX = new Map<string, Record<string, string | number>>();
  spec.series.forEach((s) => {
    s.data.forEach((point) => {
      const rawX = point[spec.x_key];
      const label = spec.x_key === "month" && typeof rawX === "number"
        ? MONTHS[rawX] : String(rawX);
      const row = byX.get(label) ?? { x: label };
      row[s.name] = point.value ?? point.y ?? 0;
      byX.set(label, row);
    });
  });
  return Array.from(byX.values());
}

/**
 * A chart's Y axis is currency, a percentage, or a plain count (days,
 * items) - never assume currency. The backend tags every chart with
 * value_format; this just renders whatever it says. Getting this wrong is
 * how a day-count chart ends up with a Rs sign on axis it (see
 * inventory_days_trend / expiry_risk - both fixed by this).
 */
function makeFormatter(format: ChartSpec["value_format"]) {
  return (v: number) => {
    if (format === "percent") return `${v.toFixed(1)}%`;
    if (format === "number") return v.toLocaleString("en-IN", { maximumFractionDigits: 0 });
    return inrCompact(v);
  };
}

export default function ChartPanel({ spec }: { spec: ChartSpec }) {
  const names = spec.series.map((s) => s.name);
  const data = mergeSeries(spec);
  const horizontal = spec.type === "hbar";
  const fmt = makeFormatter(spec.value_format);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold text-slate-700">{spec.title}</h3>
      <ResponsiveContainer width="100%" height={horizontal ? 360 : 280}>
        {spec.type === "line" ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="x" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={fmt} tick={{ fontSize: 11 }} width={80} />
            <Tooltip formatter={(v) => fmt(Number(v))} />
            <Legend />
            {spec.reference_line !== null && (
              <ReferenceLine y={spec.reference_line} stroke="#dc2626"
                             strokeDasharray="4 4" />
            )}
            {names.map((n, i) => (
              <Line key={n} type="monotone" dataKey={n}
                    stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} />
            ))}
          </LineChart>
        ) : spec.type === "donut" ? (
          <PieChart>
            <Tooltip formatter={(v) => fmt(Number(v))} />
            <Legend />
            <Pie data={data} dataKey={names[0]} nameKey="x"
                 innerRadius={60} outerRadius={100}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        ) : (
          <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            {horizontal ? (
              <>
                <XAxis type="number" tickFormatter={fmt} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="x" width={160}
                       tick={{ fontSize: 11 }} />
              </>
            ) : (
              <>
                <XAxis dataKey="x" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={fmt} tick={{ fontSize: 11 }} width={80} />
              </>
            )}
            <Tooltip formatter={(v) => fmt(Number(v))} />
            {names.length > 1 && <Legend />}
            {names.map((n, i) => (
              <Bar key={n} dataKey={n} fill={COLORS[i % COLORS.length]}
                   stackId={spec.type === "stacked_bar" ? "a" : undefined} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}