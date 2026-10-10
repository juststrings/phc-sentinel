import Link from "next/link";
import { QueueTrend } from "@/components/Charts";
import Chip from "@/components/Chip";
import DriverBars from "@/components/DriverBars";
import InsightPanel from "@/components/InsightPanel";
import LgaMap from "@/components/LgaMap";
import LgaTable from "@/components/LgaTable";
import QueueMatrix from "@/components/QueueMatrix";
import { api, monthLabel, pct } from "@/lib/api";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card px-4 py-3">
      <div className="th">{label}</div>
      <div className="text-[24px] font-bold leading-8 tabular-nums text-ink">{value}</div>
      {sub && <div className="text-[12px] text-ink-3">{sub}</div>}
    </div>
  );
}

function TopList({ title, rows, month }: { title: string; rows: any[]; month: string }) {
  return (
    <section className="card p-4">
      <h2 className="mb-2 text-[16px] font-semibold text-ink">{title}</h2>
      <ol>
        {rows.map((r, i) => (
          <li key={r.facility_id} className="flex items-start gap-3 border-b border-line py-2 last:border-0">
            <span className="w-5 pt-0.5 text-[12px] text-ink-3 tabular-nums">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <Link href={`/facility/${r.facility_id}?month=${month}`} className="text-[13px] font-medium hover:underline">{r.name}</Link>
              <div className="text-[12px] text-ink-3">{r.lga} · {r.evidence_summary}</div>
            </div>
            <Chip kind="queue" tag={r.tag} />
          </li>
        ))}
      </ol>
    </section>
  );
}

export default async function StateOverview({ searchParams }: { searchParams: Promise<{ month?: string }> }) {
  const { month: m } = await searchParams;
  const meta = await api("/meta/months");
  const month = m ?? meta.latest;
  const idx = meta.months.indexOf(month);
  const prevMonth = idx > 0 ? meta.months[idx - 1] : null;
  const [s, prev, ins, top, lgaGeo, facGeo, coords, cfg] = await Promise.all([
    api("/state/summary", month),
    prevMonth ? api("/state/summary", prevMonth) : Promise.resolve(null),
    api("/state/insights", month),
    api("/state/top", month),
    api("/geo/lgas", month),
    api("/geo/facilities", month),
    api("/meta/coords"),
    api("/meta/settings"),
  ]);
  const k = s.kpis;
  const trend = s.trend.filter((t: any) => !t.warmup);
  const omitted = s.trend.length - trend.length;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[24px] font-semibold leading-8 text-ink">State overview</h1>
        <p className="text-[13px] text-ink-3">
          {monthLabel(month)} analysis, as of {cfg.settings.calendar.analysis_lag_days} days after month end
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7"><QueueMatrix k={k} prev={prev?.kpis} /></div>
        <div className="lg:col-span-5"><InsightPanel ins={ins} month={month} /></div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Reporting completeness" value={pct(k.reporting_completeness)} sub="monthly reports received" />
        <Stat label="On-time reporting" value={pct(k.on_time_rate)} sub="by the reporting deadline" />
        <Stat label="Silent PHCs" value={String(k.silent)} sub="consecutive reports missing" />
        <Stat label="Stale commodity reports" value={String(k.stale_commodity_reports)} sub="NHLMIS overdue or absent" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-4">
          <h2 className="mb-3 text-[16px] font-semibold text-ink">LGAs by Act now share</h2>
          <LgaMap lgas={lgaGeo} facilities={facGeo} month={month} />
          <p className="mt-2 text-[12px] text-ink-3">
            {coords.outside_state} PHCs have coordinates outside Bauchi State. They are not shown on the map and still appear in the queues.
          </p>
        </section>
        <LgaTable rows={s.lgas} month={month} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card p-4 lg:col-span-2">
          <h2 className="mb-1 text-[16px] font-semibold text-ink">Queue sizes over time</h2>
          <QueueTrend data={trend} />
          <p className="text-[12px] text-ink-3">
            {omitted > 0 && `The first ${omitted} months are not shown: with no history yet, almost every PHC lands in verification. `}
            Action rises with the rainy-season malaria peak; verification tracks missing and overdue reports.
          </p>
        </section>
        <DriverBars rows={s.action_by_domain} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <TopList title="Top of the state action queue" rows={top.action} month={month} />
        <TopList title="Top of the state verification queue" rows={top.verification} month={month} />
      </div>
    </div>
  );
}
