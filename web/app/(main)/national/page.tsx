import type { Metadata } from "next";
import Link from "next/link";
import NationalCommand from "@/components/national/NationalCommand";
import { api, monthLabel } from "@/lib/api";

export const metadata: Metadata = { title: "National Command Centre" };

/** National Command Centre: state-level aggregates only. Facility detail is one click
 * away in each state portal. Payloads are precomputed state marts (a few KB). */
export default async function National({ searchParams }: {
  searchParams: Promise<{ month?: string; metric?: string; state?: string; zone?: string; q?: string; sort?: string }>;
}) {
  const sp = await searchParams;
  const meta = await api("/meta/months");
  const month = sp.month ?? meta.latest;
  const [summary, st, geo] = await Promise.all([api("/national/summary", month), api("/national/states", month), api("/national/geo")]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[12px] text-ink-3">National / {monthLabel(month, true)} analysis</p>
          <h1 className="text-[24px] font-semibold leading-8 text-ink">National Command Centre</h1>
          <p className="text-[13px] text-ink-3">
            {summary.kpis.states} states across all six geopolitical zones · state-level summaries; open a state portal for facility detail
          </p>
        </div>
        <Link className="rounded bg-[var(--brand)] px-3 py-1.5 text-[13px] font-medium text-[var(--canvas)]" href={`/national/briefing?month=${month}`}>
          Briefing mode
        </Link>
      </div>
      <NationalCommand key={month} summary={summary} states={st.states} geo={geo}
        initial={{ metric: sp.metric, state: sp.state, zone: sp.zone, q: sp.q, sort: sp.sort }} />
    </div>
  );
}
