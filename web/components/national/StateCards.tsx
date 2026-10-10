"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import StatusChip from "@/components/StatusChip";
import { int, pct } from "@/lib/api";
import StateBrief from "./StateBrief";
import StateModal, { VIEW_LABEL, viewPath, type ModalView } from "./StateModal";

const SORTS = [
  { key: "pct_act_now", label: "% Act now", worse: true },
  { key: "pct_verification", label: "% in Data Verification", worse: true },
  { key: "reporting_completeness", label: "Reporting completeness", worse: false },
  { key: "pct_stale", label: "% stale stock reports", worse: true },
  { key: "act_now", label: "Act now (count)", worse: true },
  { key: "facilities", label: "PHCs assessed", worse: true },
  { key: "state", label: "Name (A–Z)", worse: false },
];
const STATUSES = [
  ["All", "All statuses"], ["act_and_verify", "Act and verify"], ["action_load", "High action load"], ["evidence_gap", "Evidence gap"], ["watch", "Watch"],
] as const;

const field = "rounded border border-line bg-card px-2 py-1.5 text-[13px] text-ink";
const pill = (on: boolean) =>
  `rounded-full border px-2.5 py-1 text-[12px] font-medium ${on ? "border-[var(--brand)] bg-[var(--brand)] text-[var(--canvas)]" : "border-line bg-card text-ink-2 hover:bg-muted"}`;

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

/** State-level view: one card per state, filterable (search, zone, status, a single state) and sortable. Each card links to that
 *  state's overview, LGA queues and facilities. The state brief opens from the card. Filters live in the URL. */
export default function StateCards({ states, zones, month, initial }: {
  states: any[]; zones: string[]; month: string; initial: { zone?: string; state?: string; status?: string; q?: string; sort?: string; brief?: string };
}) {
  const [zone, setZone] = useState(initial.zone ?? "All");
  const [one, setOne] = useState(initial.state ?? "");
  const [status, setStatus] = useState(initial.status ?? "All");
  const [query, setQuery] = useState(initial.q ?? "");
  const [sortKey, setSortKey] = useState(SORTS.some((s) => s.key === initial.sort) ? initial.sort! : "pct_act_now");
  const [brief, setBrief] = useState<string | null>(states.some((s) => s.state_code === initial.brief) ? initial.brief! : null);
  const [modal, setModal] = useState<{ code: string; view: ModalView } | null>(null);
  const q = `?month=${month}`;

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const set = (k: string, v: string | null) => (v ? p.set(k, v) : p.delete(k));
    set("zone", zone === "All" ? null : zone);
    set("state", one || null);
    set("status", status === "All" ? null : status);
    set("q", query || null);
    set("sort", sortKey === "pct_act_now" ? null : sortKey);
    set("brief", brief);
    const qs = p.toString();
    window.history.replaceState(null, "", `${window.location.pathname}${qs ? `?${qs}` : ""}`);
  }, [zone, one, status, query, sortKey, brief]);

  const cards = useMemo(() => {
    const s = SORTS.find((x) => x.key === sortKey) ?? SORTS[0];
    const ql = query.trim().toLowerCase();
    return states
      .filter((r) =>
        (!one || r.state_code === one) && (zone === "All" || r.zone === zone) && (status === "All" || r.status === status) &&
        (!ql || r.state.toLowerCase().includes(ql) || r.zone.toLowerCase().includes(ql)))
      .sort((a, b) => s.key === "state" ? a.state.localeCompare(b.state) : s.worse ? b[s.key] - a[s.key] : a[s.key] - b[s.key]);
  }, [states, one, zone, status, query, sortKey]);

  const order = states.map((s) => s.state_code);
  const sel = brief ? states.find((s) => s.state_code === brief) : null;
  const step = (dir: number) => setBrief((c) => (c ? order[(order.indexOf(c) + dir + order.length) % order.length] : c));
  const m = SORTS.find((x) => x.key === sortKey) ?? SORTS[0];
  const ranked = useMemo(() => [...states].sort((a, b) => (m.key === "state" ? a.state.localeCompare(b.state) : m.worse ? b[m.key] - a[m.key] : a[m.key] - b[m.key])), [states, m]);
  const reset = () => { setZone("All"); setOne(""); setStatus("All"); setQuery(""); setSortKey("pct_act_now"); };
  const filtered = zone !== "All" || one || status !== "All" || query;

  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-end gap-3 p-3">
        <label className="flex flex-col gap-1 text-[12px] text-ink-3">Show one state
          <select className={`${field} min-w-[170px]`} value={one} onChange={(e) => setOne(e.target.value)}>
            <option value="">All {states.length} states</option>
            {[...states].sort((a, b) => a.state.localeCompare(b.state)).map((s) => <option key={s.state_code} value={s.state_code}>{s.state}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-ink-3">Search
          <input type="search" placeholder="State or zone" value={query} onChange={(e) => setQuery(e.target.value)} className={`${field} w-48`} />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-ink-3">Status
          <select className={field} value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-ink-3">Sort by
          <select className={field} value={sortKey} onChange={(e) => setSortKey(e.target.value)}>
            {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </label>
        {filtered && <button className="pb-1.5 text-[13px] text-ink-3 hover:underline" onClick={reset}>Reset</button>}
        <span className="ml-auto pb-1.5 text-[12px] text-ink-3">{cards.length} of {states.length} states</span>
      </div>
      <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by zone">
        {["All", ...zones].map((z) => <button key={z} aria-pressed={zone === z} onClick={() => setZone(z)} className={pill(zone === z)}>{z}</button>)}
      </div>

      {cards.length === 0 ? (
        <div className="card p-6 text-center text-ink-3">No covered state matches these filters.</div>
      ) : (
        <div className={`grid gap-3 ${cards.length === 1 ? "max-w-xl" : "sm:grid-cols-2 xl:grid-cols-3"}`}>
          {cards.map((s) => (
            <article key={s.state_code} className="card flex flex-col p-4" aria-label={s.state}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-[15px] font-semibold text-ink"><Link href={`/state/${s.state_code}${q}`} className="hover:underline">{s.state}</Link></h2>
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
              <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-3 text-[12px] font-medium">
                {(Object.keys(VIEW_LABEL) as ModalView[]).map((v) => (
                  <a
                    key={v} href={viewPath(s.state_code, v, month)}
                    onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); setModal({ code: s.state_code, view: v }); }}
                    className="rounded border border-line px-2 py-1 text-ink hover:bg-muted"
                  >{VIEW_LABEL[v]}</a>
                ))}
                <button className="ml-auto rounded border border-line px-2 py-1 text-ink hover:bg-muted" onClick={() => setBrief(s.state_code)}>Brief</button>
              </div>
            </article>
          ))}
        </div>
      )}

      {modal && (
        <StateModal code={modal.code} name={states.find((x) => x.state_code === modal.code)?.state ?? modal.code} view={modal.view} month={month}
          onView={(view) => setModal({ code: modal.code, view })} onClose={() => setModal(null)} />
      )}

      {sel && (
        <StateBrief s={sel} month={month} onClose={() => setBrief(null)} onPrev={() => step(-1)} onNext={() => step(1)}
          position={`${m.label}: ${m.key === "state" ? sel.state : pct(sel[m.key], 1)}, rank ${ranked.findIndex((r) => r.state_code === sel.state_code) + 1} of ${states.length}.`} />
      )}
    </div>
  );
}
