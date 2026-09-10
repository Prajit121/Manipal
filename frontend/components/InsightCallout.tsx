export default function InsightCallout({ insights }: { insights: string[] }) {
  if (!insights.length) return null;
  return (
    <div className="rounded-lg border border-sky-200 bg-sky-50 p-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-sky-800">
        Key observations
      </p>
      <ul className="space-y-1">
        {insights.map((text, i) => (
          <li key={i} className="text-sm text-slate-700">- {text}</li>
        ))}
      </ul>
    </div>
  );
}
