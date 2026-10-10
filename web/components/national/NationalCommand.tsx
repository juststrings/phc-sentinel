"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Chip from "@/components/Chip";
import QueueMatrix from "@/components/QueueMatrix";
import StatusChip from "@/components/StatusChip";
import { METRICS, int, monthLabel, pct } from "@/lib/api";
import NationalMap from "./NationalMap";
import StateBrief from "./StateBrief";

const SORTS = [
  ...METRICS.map((m) => ({ key: m.key, label: m.label, worse: m.worse })),
  { key: "act_now", label: "Act now (count)", worse: true },
  { key: "facilities", label: "PHCs assessed", worse: true },
  { key: "state", label: "Name (A–Z)", worse: false },
];

const field = "rounded border border-line bg-card px-2 py-1.5 text-[13px] text-ink";

function Sparkline({ values, label }: { values: number[]; label: string }) {
  if (values.length < 2) return null;
  const w = 96, h = 26, lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const pts = values.map((v, i) => [(i * w) / (values.length - 1), h - 3 - ((v - lo) / span) * (h - 6)]);
  const last = pts[pts.length - 1];
  return (
    <svg width={w} height={h} role="img" aria-label={label} style={{ overflow: "visible" }}>
      <title>{label}</title>
      <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke="var(--ink-3)" strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r={3} fill="var(--q-act)" stroke="var(--card)" strokeWidth={1.5} />
    </svg>
  );
}

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
  summary: any; states: any[]; geo: any; initial: { metric?: string; state?: string; zone?: string; q?: string; sort?: string };
}) {
  const month = summary.month;
  const k = summary.kpis;
  const prev = summary.trend.length > 1 ? summary.trend[summary.trend.findIndex((t: any) => t.analysis_month === month) - 1] : undefined;
  const [metric, setMetric] = useState(METRICS.some((m) => m.key === initial.metric) ? initial.metric! : "pct_act_now");
  const [selected, setSelected] = useState<string | null>(states.some((s) => s.state_code === initial.state) ? initial.state! : null);
  const [zone, setZone] = useState<string>(initial.zone ?? "All");
  const [query, setQuery] = useState(initial.q ?? "");
  const [sort, setSort] = useState<string>(initial.sort ?? "");
  const sortKey = sort || metric;
  const m = METRICS.find((x) => x.key === metric)!;

  // Keep the view shareable: metric, open brief, filters live in the URL (no reload).
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const set = (k: string, v: string | null) => (v ? p.set(k, v) : p.delete(k));
    set("metric", metric === "pct_act_now" ? null : metric);
    set("state", selected);
    set("zone", zone === "All" ? null : zone);
    set("q", query || null);
    set("sort", sort || null);
    const qs = p.toString();
    window.history.replaceState(null, "", `${window.location.pathname}${qs ? `?${qs}` : ""}`);
  }, [metric, selected, zone, query, sort]);

  const ranked = useMemo(() => [...states].sort((a, b) => (m.worse ? b[metric] - a[metric] : a[metric] - b[metric])), [states, metric, m.worse]);
  const cards = useMemo(() => {
    const s = SORTS.find((x) => x.key === sortKey) ?? SORTS[0];
    const ql = query.trim().toLowerCase();
    return states
      .filter((r) => (zone === "All" || r.zone === zone) && (!ql || r.state.toLowerCase().includes(ql) || r.zone.toLowerCase().includes(ql)))
      .sort((a, b) => s.key === "state" ? a.state.localeCompare(b.state) : s.worse ? b[s.key] - a[s.key] : a[s.key] - b[s.key]);
  }, [states, zone, query, sortKey]);

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
    { label: "States covered", value: `${k.states}`, sub: `of 37 · 2 per zone · ${int(k.lgas)} LGAs`, accent: "var(--ink-3)" },
    { label: "PHCs assessed", value: int(k.facilities), sub: "public primary facilities (GRID3)", accent: "var(--ink-3)" },
    { label: "Act now", value: int(k.act_now), sub: `${pct(k.pct_act_now, 1)} of PHCs`, d: <Delta now={k.act_now} prev={prev?.act_now} />, accent: "var(--q-act)" },
    { label: "Verify then act", value: int(k.verify_then_act), sub: `${pct(k.pct_verify_then_act, 1)} of PHCs`, d: <Delta now={k.verify_then_act} prev={prev?.verify_then_act} />, accent: "var(--q-verify)" },
    { label: "Do not assume safe", value: int(k.verification), sub: `${pct(k.pct_verification, 1)} in data verification`, d: <Delta now={k.verification} prev={prev?.verification} />, accent: "var(--q-dnas)" },
    { label: "Reporting complete", value: pct(k.reporting_completeness, 1), sub: `monthly reports · ${pct(k.on_time_rate)} on time`, d: <Delta now={k.reporting_completeness} prev={prev?.reporting_completeness} worse={false} asPct />, accent: "var(--s1)" },
    { label: "Stale stock reports", value: int(k.stale_commodity), sub: `NHLMIS overdue · ${pct(k.pct_stale, 1)} of PHCs`, d: <Delta now={k.pct_stale} prev={prev?.pct_stale} asPct />, accent: "var(--s1)" },
  ];

  const cells = (z: any, label: string, sub: string) => (
    <>
      <td className="px-3 py-2.5"><span className="font-medium">{label}</span></td>
      <td className="px-3 py-2.5 text-ink-3">{sub}</td>
      <td className="px-3 py-2.5 text-right tabular-nums">{int(z.facilities)}</td>
      <td className="px-3 py-2.5 text-right tabular-nums">{int(z.act_now)} <span className="text-ink-3">({pct(z.pct_act_now)})</span></td>
      <td className="px-3 py-2.5 text-right tabular-nums">{int(z.verify_then_act)}</td>
      <td className="px-3 py-2.5 text-right tabular-nums">{int(z.verification)} <span className="text-ink-3">({pct(z.pct_verification)})</span></td>
      <td className="px-3 py-2.5 text-right tabular-nums">{int(z.monitor)}</td>
      <td className="px-3 py-2.5 text-right tabular-nums">{pct(z.reporting_completeness)}</td>
      <td className="px-3 py-2.5 text-right tabular-nums">{pct(z.pct_stale)}</td>
      <td className="px-3 py-2.5"><StatusChip status={z.status} /></td>
    </>
  );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        {kpis.map((c) => (
          <div key={c.label} className="card px-3 py-3" style={{ borderLeftWidth: 4, borderLeftColor: c.accent }}>
            <div className="th">{c.label}</div>
            <div className="mt-0.5 text-[24px] font-bold leading-8 tabular-nums text-ink">{c.value}</div>
            <div className="text-[12px] text-ink-3">{c.sub}{c.d}</div>
          </div>
        ))}
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-12">
        <section className="card p-4 lg:col-span-8">
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

        <div className="space-y-4 lg:col-span-4">
          <QueueMatrix k={k} title="National risk and confidence" />
          <section className="card p-4">
            <h2 className="text-[16px] font-semibold text-ink">States by {m.label.toLowerCase()}</h2>
            <p className="mb-2 text-[12px] text-ink-3">{m.worse ? "Highest first" : "Lowest first"} · click for the brief</p>
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

      <section aria-labelledby="cards-h" className="space-y-3">
        <div>
          <h2 id="cards-h" className="text-[18px] font-semibold text-ink">State cards</h2>
          <p className="text-[13px] text-ink-3">Every covered state, with its status in words. Click a card for the state brief.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2">
            <span className="sr-only">Search states</span>
            <input type="search" placeholder="Search state or zone" value={query} onChange={(e) => setQuery(e.target.value)} className={`${field} w-56`} />
          </label>
          <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by zone">
            {["All", ...summary.zones.map((z: any) => z.zone)].map((z: string) => (
              <button
                key={z} aria-pressed={zone === z} onClick={() => setZone(z)}
                className={`rounded-full border px-2.5 py-1 text-[12px] font-medium ${zone === z ? "border-[var(--brand)] bg-[var(--brand)] text-[var(--canvas)]" : "border-line bg-card text-ink-2 hover:bg-muted"}`}
              >{z}</button>
            ))}
          </div>
          <label className="ml-auto flex items-center gap-2 text-[13px] text-ink-2">
            Sort by
            <select className={field} value={sortKey} onChange={(e) => setSort(e.target.value)}>
              {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </label>
        </div>
        {cards.length === 0 ? (
          <div className="card p-6 text-center text-ink-3">No covered state matches “{query}”{zone !== "All" ? ` in ${zone}` : ""}.</div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {cards.map((s) => (
              <button
                key={s.state_code} onClick={() => open(s.state_code)} aria-current={selected === s.state_code} aria-label={`${s.state} state brief`}
                className={`card p-4 text-left hover:bg-muted ${selected === s.state_code ? "ring-2 ring-[var(--brand)]" : ""}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-[15px] font-semibold text-ink">{s.state}</h3>
                    <div className="text-[12px] text-ink-3">{s.zone} · {int(s.facilities)} PHCs · {s.lgas} LGAs</div>
                  </div>
                  <StatusChip status={s.status} />
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
                  <div className="rounded border border-act-now-bd bg-act-now-bg px-2 py-1.5 text-act-now">
                    <div>Act now</div><b className="text-[16px] tabular-nums">{int(s.act_now)}</b> <span className="opacity-80">{pct(s.pct_act_now)}</span>
                  </div>
                  <div className="rounded border border-verify-then-act-bd bg-verify-then-act-bg px-2 py-1.5 text-verify-then-act">
                    <div>Verify then act</div><b className="text-[16px] tabular-nums">{int(s.verify_then_act)}</b>
                  </div>
                  <div className="hatch rounded border border-dashed border-do-not-assume-safe-bd bg-do-not-assume-safe-bg px-2 py-1.5 text-do-not-assume-safe">
                    <div>Do not assume safe</div><b className="text-[16px] tabular-nums">{int(s.verification)}</b> <span className="opacity-80">{pct(s.pct_verification)}</span>
                  </div>
                </div>
                <div className="mt-3 flex items-end justify-between gap-2">
                  <div className="space-y-0.5 text-[12px] text-ink-2">
                    <div>Reporting <b className="text-ink">{pct(s.reporting_completeness)}</b></div>
                    <div>Stale stock <b className="text-ink">{pct(s.pct_stale)}</b></div>
                  </div>
                  <Sparkline values={s.trend.map((t: any) => t.act_now)} label={`Act now, last ${s.trend.length} months: ${s.trend.map((t: any) => t.act_now).join(", ")}`} />
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="zones-h" className="space-y-3">
        <div>
          <h2 id="zones-h" className="text-[18px] font-semibold text-ink">Geopolitical zones compared</h2>
          <p className="text-[13px] text-ink-3">Each zone is the sum of its two demo states. Click a zone to filter the state cards.</p>
        </div>
        <div className="card overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="th border-b border-line text-left">
                <Th>Zone</Th><Th>States</Th><Th right>PHCs</Th><Th right>Act now</Th><Th right>Verify then act</Th>
                <Th right>Do not assume safe</Th><Th right>Monitor</Th><Th right>Reporting</Th><Th right>Stale stock</Th><Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {summary.zones.map((z: any) => (
                <tr
                  key={z.zone} className="cursor-pointer border-b border-line hover:bg-muted"
                  onClick={() => { setZone(z.zone); document.getElementById("cards-h")?.scrollIntoView({ behavior: "smooth" }); }}
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

      {sel && (
        <StateBrief s={sel} month={month} onClose={() => setSelected(null)} onPrev={() => step(-1)} onNext={() => step(1)}
          position={`${m.label}: ${pct(sel[metric], 1)}, rank ${ranked.findIndex((r) => r.state_code === sel.state_code) + 1} of ${states.length}.`} />
      )}
    </div>
  );
}
