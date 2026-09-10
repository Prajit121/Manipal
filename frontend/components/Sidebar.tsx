"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DASHBOARDS } from "@/lib/nav";

export default function Sidebar() {
  const path = usePathname();

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <p className="text-lg font-semibold tracking-tight text-slate-900">
          Manipal
        </p>
        <p className="text-xs text-slate-500">Pharmacy &amp; Inventory Analytics</p>
      </div>

      <nav className="flex-1 space-y-0.5 p-3">
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

      {/* Demo data is flagged in the UI, not just in the code comments. If a
          client is going to look at these numbers, they should know what they
          are looking at. */}
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
