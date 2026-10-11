"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import StatusChip from "@/components/StatusChip";
import ThemeToggle from "@/components/ThemeToggle";
import { DOMAIN_LABEL, METRICS, int, monthLabel, pct } from "@/lib/format";
import NationalMap from "./NationalMap";

const list = (xs: string[]) => (xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);

const STATUS_BOARD = [
  { key: "act_and_verify", label: "Act and verify", long: "High action load and a large evidence gap", color: "var(--q-act)" },
  { key: "action_load", label: "High action load", long: "Many PHCs need resupply or repair now", color: "var(--q-verify)" },
  { key: "evidence_gap", label: "Evidence gap", long: "Too many PHCs whose calm cannot be trusted", color: "var(--q-dnas)" },
  { key: "watch", label: "Watch", long: "Action load and evidence gap both below the alert thresholds", color: "var(--q-monitor)" },
];

const btn = "rounded border border-line bg-card px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-muted disabled:opacity-40";
const kicker = "th mb-2";
const h1 = "text-[34px] font-bold leading-[1.15] tracking-tight text-ink";

function Big({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div className="card p-5" style={{ borderTopWidth: 4, borderTopColor: color }}>
      <div className="th" style={{ color }}>{label}</div>
      <div className="mt-1 text-[48px] font-bold leading-none tabular-nums text-ink">{value}</div>
      <div className="mt-2 text-[14px] text-ink-2">{sub}</div>
    </div>
  );
}

function RankRows({ rows, value, color, sub, top }: { rows: any[]; value: (s: any) => number; color: string; sub: (s: any) => string; top: number }) {
  return (
    <div className="mt-4 space-y-1.5">
      {rows.map((s, i) => (
        <div key={s.state_code} className="grid grid-cols-[28px_minmax(150px,240px)_1fr_64px] items-center gap-3 text-[15px]">
          <span className="text-ink-3 tabular-nums">{i + 1}</span>
          <span className="font-medium text-ink">{s.state}<small className="block text-[12px] font-normal text-ink-3">{sub(s)}</small></span>
          <span className="h-3 rounded-sm bg-muted"><i className="block h-3 rounded-sm" style={{ width: `${(100 * value(s)) / top}%`, background: color }} /></span>
          <span className="text-right font-semibold tabular-nums text-ink">{pct(value(s), 1)}</span>
        </div>
      ))}
    </div>
  );
}

/** Presentation-ready national view: large type, one message per slide, arrow keys to move. */
export default function Briefing({ summary, states, geo, initialSlide }: { summary: any; states: any[]; geo: any; initialSlide: number }) {
  const k = summary.kpis;
  const month = summary.month;
  const [metric, setMetric] = useState("pct_act_now");
  const byAct = useMemo(() => [...states].sort((a, b) => b.pct_act_now - a.pct_act_now), [states]);
  const byVer = useMemo(() => [...states].sort((a, b) => b.pct_verification - a.pct_verification), [states]);
  const domain = ["malaria_commodity", "vaccine_cold_chain", "service_pressure"]
    .map((d) => ({ d, n: states.reduce((a, s) => a + s[`action_${d}`], 0) })).sort((a, b) => b.n - a.n)[0];
  const top3 = byAct.slice(0, 3).map((s) => s.state);
  const gap3 = byVer.slice(0, 3).map((s) => s.state);
  const m = METRICS.find((x) => x.key === metric)!;

  const slides = [
    {
      id: "headline", render: () => (
        <>
          <div className={kicker}>National briefing · {monthLabel(month, true)}</div>
          <h1 className={h1}>{int(k.act_now + k.verify_then_act)} primary health care facilities need resupply or repair; {int(k.verification)} more look calm on evidence too weak to trust.</h1>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Big label="PHCs assessed" value={int(k.facilities)} sub={`${k.states} states · all 6 zones`} color="var(--ink-3)" />
            <Big label="Act now" value={int(k.act_now)} sub="credible warning, current evidence" color="var(--q-act)" />
            <Big label="Verify then act" value={int(k.verify_then_act)} sub="warning on weak or stale evidence" color="var(--q-verify)" />
            <Big label="Do not assume safe" value={int(k.verification)} sub={`${pct(k.reporting_completeness)} of monthly reports received`} color="var(--q-dnas)" />
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="States by status">
            {STATUS_BOARD.map((st) => {
              const xs = states.filter((s) => s.status === st.key);
              return (
                <div key={st.key} className="card p-4" style={{ borderTopWidth: 4, borderTopColor: st.color }}>
                  <h3 className="text-[15px] font-semibold text-ink">{st.label} <small className="font-normal text-ink-3">{xs.length} state{xs.length === 1 ? "" : "s"}</small></h3>
                  <p className="text-[12px] text-ink-3">{st.long}.</p>
                  <ul className="mt-2 space-y-0.5 text-[14px] text-ink-2">
                    {xs.length ? xs.map((s) => <li key={s.state_code}>{s.state}</li>) : <li className="text-ink-3">None this month</li>}
                  </ul>
                </div>
              );
            })}
          </div>
        </>
      ),
    },
    {
      id: "map", render: () => (
        <>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div><div className={kicker}>The national picture</div><h1 className={h1}>{m.label} by state</h1></div>
            <div className="flex flex-wrap gap-1" role="group" aria-label="Map metric">
              {METRICS.map((x) => (
                <button key={x.key} aria-pressed={metric === x.key} onClick={() => setMetric(x.key)}
                  className={`rounded border px-3 py-2 text-[14px] font-medium ${metric === x.key ? "border-[var(--brand)] bg-[var(--brand)] text-[var(--canvas)]" : "border-line bg-card text-ink-2 hover:bg-muted"}`}>{x.label}</button>
              ))}
            </div>
          </div>
          <div className="card mt-4 p-3"><NationalMap geo={geo} states={states} metric={metric} height={560} /></div>
        </>
      ),
    },
    {
      id: "act", render: () => (
        <>
          <div className={kicker}>Where to act</div>
          <h1 className={h1}>{list(top3)} have the highest share of PHCs needing action now.</h1>
          <p className="mt-2 max-w-3xl text-[17px] text-ink-2">{DOMAIN_LABEL[domain.d]} drive most resource action nationally ({int(domain.n)} of {int(k.action)} PHCs).</p>
          <RankRows rows={byAct} value={(s) => s.pct_act_now} top={byAct[0].pct_act_now} color="var(--q-act)" sub={(s) => `${s.zone} · ${int(s.act_now)} of ${int(s.facilities)} PHCs`} />
        </>
      ),
    },
    {
      id: "verify", render: () => (
        <>
          <div className={kicker}>Where the evidence is weakest</div>
          <h1 className={h1}>In {list(gap3)}, the largest share of PHCs cannot be called safe.</h1>
          <p className="mt-2 max-w-3xl text-[17px] text-ink-2">These facilities show no credible warning, but their reports are missing, late, stale or incoherent. Sentinel routes them to verification instead of showing them green.</p>
          <RankRows rows={byVer} value={(s) => s.pct_verification} top={byVer[0].pct_verification} color="var(--q-dnas)" sub={(s) => `reporting ${pct(s.reporting_completeness)} · stale stock ${pct(s.pct_stale)}`} />
        </>
      ),
    },
    {
      id: "zones", render: () => (
        <>
          <div className={kicker}>Zones compared</div>
          <h1 className={h1}>Six geopolitical zones, side by side</h1>
          <div className="card mt-4 overflow-x-auto">
            <table className="w-full text-[15px]">
              <thead>
                <tr className="th border-b border-line text-left">
                  <th className="px-4 py-3">Zone</th><th className="px-4 py-3 text-right">PHCs</th><th className="px-4 py-3 text-right">Act now</th>
                  <th className="px-4 py-3 text-right">Verify then act</th><th className="px-4 py-3 text-right">Do not assume safe</th><th className="px-4 py-3 text-right">Reporting</th><th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {summary.zones.map((z: any) => (
                  <tr key={z.zone} className="border-b border-line">
                    <td className="px-4 py-3"><b className="text-ink">{z.zone}</b><div className="text-[13px] text-ink-3">{states.filter((s) => s.zone === z.zone).map((s) => s.state).join(", ")}</div></td>
                    <td className="px-4 py-3 text-right tabular-nums">{int(z.facilities)}</td><td className="px-4 py-3 text-right tabular-nums">{int(z.act_now)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{int(z.verify_then_act)}</td><td className="px-4 py-3 text-right tabular-nums">{int(z.verification)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{pct(z.reporting_completeness)}</td><td className="px-4 py-3"><StatusChip status={z.status} /></td>
                  </tr>
                ))}
                <tr className="bg-muted font-semibold">
                  <td className="px-4 py-3">All covered states</td><td className="px-4 py-3 text-right tabular-nums">{int(k.facilities)}</td><td className="px-4 py-3 text-right tabular-nums">{int(k.act_now)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{int(k.verify_then_act)}</td><td className="px-4 py-3 text-right tabular-nums">{int(k.verification)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{pct(k.reporting_completeness)}</td><td className="px-4 py-3"><StatusChip status={k.status} /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      ),
    },
    {
      id: "ask", render: () => (
        <>
          <div className={kicker}>What this means</div>
          <div className="text-[40px] font-bold leading-tight tracking-tight text-ink">Low observed risk with low confidence is not safe.</div>
          <div className="mt-6 grid gap-3 lg:grid-cols-3">
            {[
              ["Act", "var(--q-act)", `Prioritise resupply and cold-chain repair for ${int(k.act_now)} PHCs, led by ${list(top3)}.`],
              ["Verify, then act", "var(--q-verify)", `Confirm stock within days for ${int(k.verify_then_act)} PHCs before moving supplies, and prepare the response in parallel.`],
              ["Recover the evidence", "var(--q-dnas)", `Follow up missing and stale reports for ${int(k.verification)} PHCs; ${int(k.stale_commodity)} have an overdue NHLMIS stock report.`],
            ].map(([label, color, text]) => (
              <div key={label} className="card p-5" style={{ borderTopWidth: 4, borderTopColor: color }}>
                <div className="th" style={{ color }}>{label}</div>
                <p className="mt-1 text-[19px] leading-7 text-ink">{text}</p>
              </div>
            ))}
          </div>
          <p className="mt-6 max-w-3xl text-[14px] text-ink-3">
            Facility lists are real (GRID3 v3.0); operational figures are simulated to demonstrate the method. A pilot would run on a state&apos;s own DHIS2 and NHLMIS exports with no new reporting burden.
          </p>
        </>
      ),
    },
  ];

  const [i, setI] = useState(Math.min(Math.max(initialSlide, 0), slides.length - 1));
  const go = useCallback((n: number) => setI((c) => Math.min(Math.max(c + n, 0), slides.length - 1)), [slides.length]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input,select,textarea")) return;
      if (["ArrowRight", "PageDown", " "].includes(e.key)) { e.preventDefault(); go(1); }
      if (["ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); go(-1); }
      if (e.key === "Home") setI(0);
      if (e.key === "End") setI(slides.length - 1);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [go, slides.length]);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    p.set("slide", String(i + 1));
    window.history.replaceState(null, "", `${window.location.pathname}?${p}`);
  }, [i]);

  return (
    <div className="flex min-h-[calc(100vh-var(--banner-h,32px))] flex-col bg-canvas">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-card px-5 py-3 print:hidden">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-[15px] font-bold text-ink">PHC Sentinel</Link>
          <span className="text-[13px] text-ink-3">National briefing · {monthLabel(month, true)}</span>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button className={btn} onClick={() => window.print()}>Print</button>
          <Link className={btn} href={`/national?month=${month}`}>Exit briefing</Link>
        </div>
      </div>
      <section className="mx-auto w-full max-w-[1200px] flex-1 px-6 py-8" aria-live="polite" aria-label={`Slide ${i + 1} of ${slides.length}`}>{slides[i].render()}</section>
      <div className="flex items-center justify-center gap-4 border-t border-line bg-card px-5 py-3 print:hidden">
        <button className={btn} onClick={() => go(-1)} disabled={i === 0} aria-label="Previous slide">← Previous</button>
        <div className="flex gap-1.5">
          {slides.map((s, n) => (
            <button key={s.id} aria-label={`Slide ${n + 1}`} aria-current={n === i} onClick={() => setI(n)}
              className={`h-2.5 w-2.5 rounded-full ${n === i ? "bg-[var(--brand)]" : "bg-line"}`} />
          ))}
        </div>
        <span className="min-w-12 text-center text-[13px] tabular-nums text-ink-3">{i + 1} / {slides.length}</span>
        <button className="rounded bg-[var(--brand)] px-3 py-1.5 text-[13px] font-medium text-[var(--canvas)] disabled:opacity-40" onClick={() => go(1)} disabled={i === slides.length - 1} aria-label="Next slide">Next →</button>
      </div>
    </div>
  );
}
