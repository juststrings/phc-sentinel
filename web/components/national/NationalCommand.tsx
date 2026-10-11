"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import QueueMatrix from "@/components/QueueMatrix";
import StatusChip from "@/components/StatusChip";
import { METRICS, int, monthLabel, pct } from "@/lib/format";
import NationalMap from "./NationalMap";
import StateBrief from "./StateBrief";

function Delta({ now, prev, worse = true, asPct = false }: { now: number; prev?: number; worse?: boolean; asPct?: boolean }) {
  if (prev == null) return null;
  const d = now - prev;
  if (Math.abs(d) < (asPct ? 0.0005 : 0.5)) return <span className="ml-1.5 text-ink-3">no change</span>;
  const bad = worse ? d > 0 : d < 0;
  const txt = asPct ? `${d > 0 ? "+" : "−"}${Math.abs(d * 100).toFixed(1)} pts` : `${d > 0 ? "+" : "−"}${Math.abs(Math.round(d)).toLocaleString("en-GB")}`;
  return (
    <span className="ml-1.5 font-medium" style={{ color: bad ? "var(--q-act)" : "var(--q-monitor)" }} title="vs previous month">
      {d > 0 ? "▲" : "▼"} {txt}
    </span>
  );
}

function Th({ children, right }: { children?: React.ReactNode; right?: boolean }) {
  return <th className={`px-3 py-2 ${right ? "text-right" : ""}`}>{children}</th>;
}

export default function NationalCommand({ summary, states, geo, initial }: {
  summary: any; states: any[]; geo: any; initial: { metric?: string; state?: string };
}) {
  const month = summary.month;
  const k = summary.kpis;
  const prev = summary.trend.length > 1 ? summary.trend[summary.trend.findIndex((t: any) => t.analysis_month === month) - 1] : undefined;
  const [metric, setMetric] = useState(METRICS.some((m) => m.key === initial.metric) ? initial.metric! : "pct_act_now");
  const [selected, setSelected] = useState<string | null>(states.some((s) => s.state_code === initial.state) ? initial.state! : null);
  const router = useRouter();
  const m = METRICS.find((x) => x.key === metric)!;

  // Keep the view shareable: metric, open brief, filters live in the URL (no reload).
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const set = (k: string, v: string | null) => (v ? p.set(k, v) : p.delete(k));
    set("metric", metric === "pct_act_now" ? null : metric);
    set("state", selected);
    const qs = p.toString();
    window.history.replaceState(null, "", `${window.location.pathname}${qs ? `?${qs}` : ""}`);
  }, [metric, selected]);

  const ranked = useMemo(() => [...states].sort((a, b) => (m.worse ? b[metric] - a[metric] : a[metric] - b[metric])), [states, metric, m.worse]);
  const order = states.map((s) => s.state_code);
  const open = useCallback((code: string) => setSelected(code), []);
  const step = useCallback((dir: number) => setSelected((c) => {
    if (!c) return c;
    const i = order.indexOf(c);
    return order[(i + dir + order.length) % order.length];
  }), [order]);
  const sel = selected ? states.find((s) => s.state_code === selected) : null;
  const maxRank = Math.max(...states.map((s) => s[metric] ?? 0), 0.0001);

  const kpis = [
    { label: "PHCs assessed", value: int(k.facilities), sub: `${k.states} states · ${int(k.lgas)} LGAs`, accent: "var(--ink-3)" },
    { label: "Act now", value: int(k.act_now), sub: `${pct(k.pct_act_now, 1)} of PHCs`, d: <Delta now={k.act_now} prev={prev?.act_now} />, accent: "var(--q-act)" },
    { label: "Verify then act", value: int(k.verify_then_act), sub: `${pct(k.pct_verify_then_act, 1)} of PHCs`, d: <Delta now={k.verify_then_act} prev={prev?.verify_then_act} />, accent: "var(--q-verify)" },
    { label: "Do not assume safe", value: int(k.verification), sub: `${pct(k.pct_verification, 1)} in data verification`, d: <Delta now={k.verification} prev={prev?.verification} />, accent: "var(--q-dnas)" },
    { label: "Reporting complete", value: pct(k.reporting_completeness, 1), sub: `monthly reports · ${pct(k.on_time_rate)} on time`, d: <Delta now={k.reporting_completeness} prev={prev?.reporting_completeness} worse={false} asPct />, accent: "var(--s1)" },
  ];

  const cells = (z: any, label: string, sub: string) => (
    <>
      <td className="whitespace-nowrap px-3 py-2.5"><span className="font-medium">{label}</span><div className="text-[11px] font-normal text-ink-3">{sub}</div></td>
      <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums">{int(z.facilities)}</td>
      <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums">{int(z.act_now)} <span className="text-ink-3">({pct(z.pct_act_now)})</span></td>
      <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums">{int(z.verify_then_act)}</td>
      <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums">{int(z.verification)} <span className="text-ink-3">({pct(z.pct_verification)})</span></td>
      <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums">{pct(z.reporting_completeness)}</td>
      <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums">{pct(z.pct_stale)}</td>
      <td className="px-3 py-2.5"><StatusChip status={z.status} /></td>
    </>
  );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {kpis.map((c) => (
          <div key={c.label} className="card px-3 py-3" style={{ borderLeftWidth: 4, borderLeftColor: c.accent }}>
            <div className="th">{c.label}</div>
            <div className="mt-0.5 text-[24px] font-bold leading-8 tabular-nums text-ink">{c.value}</div>
            <div className="text-[12px] text-ink-3">{c.sub}{c.d}</div>
          </div>
        ))}
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-12">
      <div className="space-y-6 lg:col-span-8">
        <section className="card p-4">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-[16px] font-semibold text-ink">Where attention is needed</h2>
              <p className="text-[12px] text-ink-3">Hover a state for its numbers; click a covered state for its brief.</p>
            </div>
            <div className="flex flex-wrap gap-1" role="group" aria-label="Map metric">
              {METRICS.map((x) => (
                <button
                  key={x.key} aria-pressed={metric === x.key} onClick={() => setMetric(x.key)}
                  className={`rounded border px-2.5 py-1 text-[12px] font-medium ${metric === x.key ? "border-[var(--brand)] bg-[var(--brand)] text-[var(--canvas)]" : "border-line bg-card text-ink-2 hover:bg-muted"}`}
                >{x.label}</button>
              ))}
            </div>
          </div>
          <NationalMap geo={geo} states={states} metric={metric} selected={selected} onSelect={open} />
        </section>
      <section aria-labelledby="zones-h" className="space-y-3">
        <div>
          <h2 id="zones-h" className="text-[18px] font-semibold text-ink">Geopolitical zones compared</h2>
          <p className="text-[13px] text-ink-3">Each zone is the sum of its two demo states. Click a zone to see its states.</p>
        </div>
        <div className="card overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="th border-b border-line text-left">
                <Th>Zone</Th><Th right>PHCs</Th><Th right>Act now</Th><Th right>Verify then act</Th>
                <Th right>Do not assume safe</Th><Th right>Reporting</Th><Th right>Stale stock</Th><Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {summary.zones.map((z: any) => (
                <tr
                  key={z.zone} className="cursor-pointer border-b border-line hover:bg-muted" title={`Show the ${z.zone} states`}
                  onClick={() => router.push(`/states?zone=${encodeURIComponent(z.zone)}&month=${month}`)}
                >
                  {cells(z, z.zone, states.filter((s) => s.zone === z.zone).map((s) => s.state).join(", "))}
                </tr>
              ))}
              <tr className="bg-muted font-semibold">{cells(k, "All covered states", `${k.states} states`)}</tr>
            </tbody>
          </table>
        </div>
        <p className="text-[12px] text-ink-3">National and zone figures are sums of state figures; rates are recomputed from the summed counts.</p>
      </section>
      </div>

        <div className="space-y-4 lg:col-span-4">
          <QueueMatrix k={k} title="National risk and confidence" />
          <section className="card p-4">
            <h2 className="text-[16px] font-semibold text-ink">States by {m.label.toLowerCase()}</h2>
            <p className="mb-2 text-[12px] text-ink-3">{m.worse ? "Highest first" : "Lowest first"} · click for the brief · <Link href={`/states?month=${month}`} className="font-medium text-ink underline-offset-2 hover:underline">All states →</Link></p>
            <ol>
              {ranked.map((s, i) => (
                <li key={s.state_code}>
                  <button
                    onClick={() => open(s.state_code)} aria-label={`${s.state}: ${pct(s[metric], 1)}. Open brief`}
                    className="grid w-full grid-cols-[20px_1fr_auto] items-center gap-2 rounded px-1 py-1.5 text-left hover:bg-muted"
                  >
                    <span className="text-[12px] text-ink-3 tabular-nums">{i + 1}</span>
                    <span className="min-w-0">
                      <span className="text-[13px] font-medium text-ink">{s.state}</span> <span className="text-[11px] text-ink-3">{s.zone}</span>
                      <span className="mt-1 block h-1.5 rounded-sm bg-muted"><i className="block h-1.5 rounded-sm bg-[var(--q-act)]" style={{ width: `${(100 * (s[metric] ?? 0)) / maxRank}%` }} /></span>
                    </span>
                    <span className="text-[13px] font-semibold tabular-nums text-ink">{pct(s[metric], 1)}</span>
                  </button>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>

      {sel && (
        <StateBrief s={sel} month={month} onClose={() => setSelected(null)} onPrev={() => step(-1)} onNext={() => step(1)}
          position={`${m.label}: ${pct(sel[metric], 1)}, rank ${ranked.findIndex((r) => r.state_code === sel.state_code) + 1} of ${states.length}.`} />
      )}
    </div>
  );
}
