import Link from "next/link";
import { notFound } from "next/navigation";
import Chip from "@/components/Chip";
import LgaMap from "@/components/LgaMap";
import LgaSelect from "@/components/LgaSelect";
import StateSelect from "@/components/StateSelect";
import WorkList from "@/components/WorkList";
import { api, apiOrNull, monthLabel, pct } from "@/lib/api";
import { QUEUE_TABS, tabRows } from "@/lib/queues";
import { QUEUE_CLASS, queueStyle } from "@/lib/tokens";

export default async function LgaQueues({ params, searchParams }: {
  params: Promise<{ code: string; id: string }>; searchParams: Promise<{ month?: string; tab?: string }>;
}) {
  const { code, id } = await params;
  const { month: m, tab = "act-now" } = await searchParams;
  const meta = await api("/meta/months");
  const month = m ?? meta.latest;
  const d = await apiOrNull(`/state/${code}/lga/${id}/queue`, month);
  if (!d) notFound();
  const [meta2, summary, lgaGeo, facGeo] = await Promise.all([
    api("/meta/states"), api(`/state/${code}/summary`, month), api(`/state/${code}/geo/lgas`, month), api(`/state/${code}/geo/facilities?lga_id=${id}`, month),
  ]);
  const l = d.lga;
  const active = QUEUE_TABS.find((t) => t.key === tab) ?? QUEUE_TABS[0];
  const counts: Record<string, number> = {
    "act-now": l.act_now, "verify-then-act": l.verify_then_act, "do-not-assume-safe": l.verification, monitor: l.monitor,
  };
  const rows = tabRows(d, active.tag, active.source);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[12px] text-ink-3"><Link href={`/national?month=${month}`} className="hover:underline">National</Link> /{" "}
            <Link href={`/state/${code}?month=${month}`} className="hover:underline">{d.state.name}</Link> / LGA queues</p>
          <div className="flex flex-wrap items-end gap-3">
            <StateSelect states={meta2.states} value={code} view="lga" />
            <LgaSelect lgas={summary.lgas} value={id} code={code} />
            <h1 className="sr-only">{l.lga} LGA queues</h1>
          </div>
          <p className="mt-1 text-[13px] text-ink-3">
            {l.facilities} PHCs · reporting {pct(l.reporting_completeness)} complete · {pct(l.on_time_rate)} on time ·
            ranked {l.lga_rank} of {summary.lgas.length} LGAs · {monthLabel(month)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {QUEUE_TABS.map((t) => <Chip key={t.key} kind="queue" tag={t.tag} count={counts[t.key]} />)}
        </div>
      </div>

      <section className="card">
        <div className="flex gap-1 overflow-x-auto border-b border-line px-2" role="tablist">
          {QUEUE_TABS.map((t) => {
            const on = t.key === active.key;
            const s = queueStyle(t.tag);
            return (
              <Link
                key={t.key} role="tab" aria-selected={on}
                href={`/state/${code}/lga/${id}?month=${month}&tab=${t.key}`}
                className={`flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-3 text-[13px] font-medium ${
                  on ? `${QUEUE_CLASS[s.token].text} border-current` : "border-transparent text-ink-2 hover:text-ink"
                }`}
              >
                {s.label}
                <span className="rounded-full bg-muted px-1.5 text-[11px] tabular-nums text-ink-2">{counts[t.key]}</span>
              </Link>
            );
          })}
        </div>
        <WorkList
          key={`${id}-${active.key}-${month}`}
          rows={rows}
          month={month}
          code={code}
          filename={`${l.lga}-${active.key}-${month}.csv`.replace(/\s+/g, "-").toLowerCase()}
        />
      </section>

      <section className="card p-4">
        <h2 className="mb-3 text-[16px] font-semibold text-ink">{l.lga} PHCs by queue</h2>
        <LgaMap lgas={lgaGeo} facilities={facGeo} month={month} focusLga={id} stateCode={code} />
      </section>
    </div>
  );
}
