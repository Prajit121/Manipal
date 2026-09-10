// Table cells are formatted here; KPI cards use the backend's display string
// directly so the two can never disagree.

export function inrFull(value: number): string {
  const v = Math.round(Math.abs(value));
  const sign = value < 0 ? "-" : "";
  const s = String(v);
  if (s.length <= 3) return `${sign}₹${s}`;
  const last3 = s.slice(-3);
  let rest = s.slice(0, -3);
  const parts: string[] = [];
  while (rest.length > 2) {
    parts.unshift(rest.slice(-2));
    rest = rest.slice(0, -2);
  }
  if (rest) parts.unshift(rest);
  return `${sign}₹${parts.join(",")},${last3}`;
}

export function inrCompact(value: number): string {
  const v = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (v >= 1e7) return `${sign}₹${(v / 1e7).toFixed(2)} Cr`;
  if (v >= 1e5) return `${sign}₹${(v / 1e5).toFixed(2)} L`;
  if (v >= 1e3) return `${sign}₹${(v / 1e3).toFixed(1)} K`;
  return `${sign}₹${v.toFixed(0)}`;
}

export function numberFull(value: number): string {
  return inrFull(value).replace("₹", "");
}

export function formatCell(value: string | number, type: string): string {
  if (value === null || value === undefined) return "—";
  if (type === "currency") return inrFull(Number(value));
  if (type === "number") return numberFull(Number(value));
  if (type === "percent") return `${Number(value).toFixed(2)}%`;
  return String(value);
}
