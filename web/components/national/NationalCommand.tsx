"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { QueueTag, StatusPill } from "@/components/Tags";
import { METRICS, TAG_STYLE, int, monthLabel, pct } from "@/lib/api";
import NationalMap from "./NationalMap";
import StateBrief from "./StateBrief";

const SORTS = [
  ...METRICS.map((m) => ({ key: m.key, label: m.label, worse: m.worse })),
  { key: "act_now", label: "Act now (count)", worse: true },
  { key: "facilities", label: "PHCs assessed", worse: true },
  { key: "state", label: "Name (A–Z)", worse: false },
];

function Sparkline({ values, label }: { values: number[]; label: string }) {
  if (values.length < 2) return null;
  const w = 96, h = 26, lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const pts = values.map((v, i) => [(i * w) / (values.length - 1), h - 3 - ((v - lo) / span) * (h - 6)]);
  const last = pts[pts.length - 1];
  return (
    <svg width={w} height={h} role="img" aria-label={label} style={{ overflow: "visible" }}>
      <title>{label}</title>
      <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke="var(--text-secondary)" strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r={3} fill="var(--st-critical)" stroke="var(--surface-1)" strokeWidth={1.5} />
    </svg>
  );
}

function Delta({ now, prev, worse = true, asPct = false }: { now: number; prev?: number; worse?: boolean; asPct?: boolean }) {
  if (prev == null) return null;
  const d = now - prev;
  if (Math.abs(d) < (asPct ? 0.0005 : 0.5)) return <span className="delta muted">no change</span>;
  const bad = worse ? d > 0 : d < 0;
  const txt = asPct ? `${d > 0 ? "+" : "−"}${Math.abs(d * 100).toFixed(1)} pts` : `${d > 0 ? "+" : "−"}${Math.abs(Math.round(d)).toLocaleString("en-GB")}`;
  return <span className="delta" style={{ color: bad ? "var(--st-critical)" : "var(--st-good)" }} title="vs previous month">{d > 0 ? "▲" : "▼"} {txt}</span>;
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
    { label: "States covered", value: `${k.states}`, sub: `of 37 · 2 per zone · ${int(k.lgas)} LGAs`, accent: "var(--brand)" },
    { label: "PHCs assessed", value: int(k.facilities), sub: "public primary facilities (GRID3)", accent: "var(--brand)" },
    { label: "Act now", icon: "ACT NOW", value: int(k.act_now), sub: `${pct(k.pct_act_now, 1)} of PHCs`, d: <Delta now={k.act_now} prev={prev?.act_now} />, accent: TAG_STYLE["ACT NOW"].color },
    { label: "Verify then act", icon: "VERIFY THEN ACT", value: int(k.verify_then_act), sub: `${pct(k.pct_verify_then_act, 1)} of PHCs`, d: <Delta now={k.verify_then_act} prev={prev?.verify_then_act} />, accent: TAG_STYLE["VERIFY THEN ACT"].color },
    { label: "Do not assume safe", icon: "DO NOT ASSUME SAFE", value: int(k.verification), sub: `${pct(k.pct_verification, 1)} in data verification`, d: <Delta now={k.verification} prev={prev?.verification} />, accent: TAG_STYLE["DO NOT ASSUME SAFE"].color },
    { label: "Reporting complete", value: pct(k.reporting_completeness, 1), sub: `monthly reports · ${pct(k.on_time_rate)} on time`, d: <Delta now={k.reporting_completeness} prev={prev?.reporting_completeness} worse={false} asPct />, accent: "var(--series-1)" },
    { label: "Stale stock reports", value: int(k.stale_commodity), sub: `NHLMIS overdue · ${pct(k.pct_stale, 1)} of PHCs`, d: <Delta now={k.pct_stale} prev={prev?.pct_stale} asPct />, accent: "var(--series-1)" },
  ];

  return (
    <>
      <div className="grid g-kpi7" style={{ marginBottom: 16 }}>
        {kpis.map((c) => (
          <div className="card kpi accent" key={c.label} style={{ ["--kpi-accent" as any]: c.accent }}>
            <div className="label">
              {c.icon && <span aria-hidden className="ico" style={{ color: TAG_STYLE[c.icon].color }}>{TAG_STYLE[c.icon].icon}</span>}
              {c.label}
            </div>
            <div className="value num">{c.value}</div>
            <div className="sub">{c.sub}{c.d}</div>
          </div>
        ))}
      </div>

      <div className="grid g-map">
        <div className="card map-card">
          <div className="card-head">
            <div>
              <h2>Where attention is needed</h2>
              <p>Hover a state for its numbers; click a covered state for its brief.</p>
            </div>
            <div className="seg" role="group" aria-label="Map metric">
              {METRICS.map((x) => (
                <button key={x.key} aria-pressed={metric === x.key} onClick={() => setMetric(x.key)}>{x.label}</button>
              ))}
            </div>
          </div>
          <NationalMap geo={geo} states={states} metric={metric} selected={selected} onSelect={open} />
        </div>

        <div className="stack">
          <div className="card">
            <div className="card-head"><div><h2>National Risk × confidence</h2><p>All {int(k.facilities)} PHCs, {monthLabel(month)}</p></div></div>
            <div className="matrix compact">
              <div />
              <div className="h">High / moderate confidence</div>
              <div className="h">Low confidence</div>
              <div className="h">High / critical risk</div>
              <div className="cell"><div className="big num">{int(k.act_now)}</div><QueueTag tag="ACT NOW" /></div>
              <div className="cell"><div className="big num">{int(k.verify_then_act)}</div><QueueTag tag="VERIFY THEN ACT" /></div>
              <div className="h">Normal / watch risk</div>
              <div className="cell"><div className="big num">{int(k.monitor)}</div><QueueTag tag="MONITOR" /></div>
              <div className="cell"><div className="big num">{int(k.verification)}</div><QueueTag tag="DO NOT ASSUME SAFE" /></div>
            </div>
          </div>
          <div className="card">
            <div className="card-head"><div><h2>States by {m.label.toLowerCase()}</h2><p>{m.worse ? "Highest first" : "Lowest first"} · click for the brief</p></div></div>
            <ol className="rank-list">
              {ranked.map((s, i) => (
                <li key={s.state_code}>
                  <button onClick={() => open(s.state_code)} aria-label={`${s.state}: ${pct(s[metric], 1)}. Open brief`}>
                    <span className="muted num">{i + 1}</span>
                    <span>
                      <strong>{s.state}</strong> <span className="muted" style={{ fontSize: 12 }}>{s.zone}</span>
                      <div className="bar"><i style={{ width: `${(100 * (s[metric] ?? 0)) / maxRank}%` }} /></div>
                    </span>
                    <span className="val">{pct(s[metric], 1)}</span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>

      <section className="section" aria-labelledby="cards-h">
        <div className="section-head">
          <div>
            <h2 id="cards-h">State cards</h2>
            <p>Every covered state, with its status in words. Click a card for the state brief.</p>
          </div>
        </div>
        <div className="toolbar">
          <div className="left">
            <label className="search">
              <span className="sr-only">Search states</span>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
              <input type="search" placeholder="Search state or zone" value={query} onChange={(e) => setQuery(e.target.value)} />
            </label>
            <div className="chips" role="group" aria-label="Filter by zone">
              {["All", ...summary.zones.map((z: any) => z.zone)].map((z: string) => (
                <button key={z} className="chip-btn" aria-pressed={zone === z} onClick={() => setZone(z)}>{z}</button>
              ))}
            </div>
          </div>
          <div className="right">
            <label className="secondary" style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
              Sort by
              <select value={sortKey} onChange={(e) => setSort(e.target.value)}>
                {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
              </select>
            </label>
          </div>
        </div>
        {cards.length === 0 ? <div className="card empty">No covered state matches “{query}”{zone !== "All" ? ` in ${zone}` : ""}.</div> : (
          <div className="state-cards">
            {cards.map((s) => (
              <button key={s.state_code} className="state-card" aria-current={selected === s.state_code} onClick={() => open(s.state_code)}
                aria-label={`${s.state} state brief`}>
                <div className="top">
                  <div><h3>{s.state}</h3><div className="zone">{s.zone} · {int(s.facilities)} PHCs · {s.lgas} LGAs</div></div>
                  <StatusPill status={s.status} />
                </div>
                <div className="nums">
                  <div><span>▲ Act now</span><b>{int(s.act_now)}<em>{pct(s.pct_act_now)}</em></b></div>
                  <div><span>◆ Verify then act</span><b>{int(s.verify_then_act)}</b></div>
                  <div><span>? Do not assume safe</span><b>{int(s.verification)}<em>{pct(s.pct_verification)}</em></b></div>
                </div>
                <div className="foot">
                  <div className="metrics">
                    <span>Reporting <b>{pct(s.reporting_completeness)}</b></span>
                    <span>Stale stock <b>{pct(s.pct_stale)}</b></span>
                  </div>
                  <Sparkline values={s.trend.map((t: any) => t.act_now)} label={`Act now, last ${s.trend.length} months: ${s.trend.map((t: any) => t.act_now).join(", ")}`} />
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="section" aria-labelledby="zones-h">
        <div className="section-head">
          <div><h2 id="zones-h">Geopolitical zones compared</h2><p>Each zone is the sum of its two demo states. Click a zone to filter the state cards.</p></div>
        </div>
        <div className="card" style={{ padding: 0, overflowX: "auto" }}>
          <table className="data">
            <thead>
              <tr>
                <th>Zone</th><th>States</th><th className="n">PHCs</th><th className="n">Act now</th><th className="n">Verify then act</th>
                <th className="n">Do not assume safe</th><th className="n">Monitor</th><th className="n">Reporting</th><th className="n">Stale stock</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {summary.zones.map((z: any) => (
                <tr key={z.zone} className="clickable" onClick={() => { setZone(z.zone); document.getElementById("cards-h")?.scrollIntoView({ behavior: "smooth" }); }}>
                  <td><strong>{z.zone}</strong></td>
                  <td className="secondary">{states.filter((s) => s.zone === z.zone).map((s) => s.state).join(", ")}</td>
                  <td className="n">{int(z.facilities)}</td>
                  <td className="n">{int(z.act_now)} <span className="muted">({pct(z.pct_act_now)})</span></td>
                  <td className="n">{int(z.verify_then_act)}</td>
                  <td className="n">{int(z.verification)} <span className="muted">({pct(z.pct_verification)})</span></td>
                  <td className="n">{int(z.monitor)}</td>
                  <td className="n">{pct(z.reporting_completeness)}</td>
                  <td className="n">{pct(z.pct_stale)}</td>
                  <td><StatusPill status={z.status} /></td>
                </tr>
              ))}
              <tr className="total">
                <td>All covered states</td><td className="secondary">{k.states} states</td>
                <td className="n">{int(k.facilities)}</td>
                <td className="n">{int(k.act_now)} <span className="muted">({pct(k.pct_act_now)})</span></td>
                <td className="n">{int(k.verify_then_act)}</td>
                <td className="n">{int(k.verification)} <span className="muted">({pct(k.pct_verification)})</span></td>
                <td className="n">{int(k.monitor)}</td>
                <td className="n">{pct(k.reporting_completeness)}</td>
                <td className="n">{pct(k.pct_stale)}</td>
                <td><StatusPill status={k.status} /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="note">National and zone figures are sums of state figures; rates are recomputed from the summed counts.</p>
      </section>

      {sel && (
        <StateBrief s={sel} month={month} onClose={() => setSelected(null)} onPrev={() => step(-1)} onNext={() => step(1)}
          position={`${m.label}: ${pct(sel[metric], 1)}, rank ${ranked.findIndex((r) => r.state_code === sel.state_code) + 1} of ${states.length}.`} />
      )}
    </>
  );
}
