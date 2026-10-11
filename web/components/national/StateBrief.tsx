"use client";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import QueueMatrix from "@/components/QueueMatrix";
import StatusChip from "@/components/StatusChip";
import { DOMAIN_LABEL, int, monthLabel, pct } from "@/lib/format";

const short = (m: string) => {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo - 1, 1).toLocaleString("en-GB", { month: "short" });
};
const axis = { stroke: "var(--line)", tick: { fill: "var(--ink-3)", fontSize: 11 }, tickLine: false };
const tip = {
  contentStyle: { background: "var(--card)", border: "1px solid var(--line)", borderRadius: 6, fontSize: 12, color: "var(--ink)" },
  labelStyle: { color: "var(--ink-2)", fontWeight: 600 },
};

const iconBtn = "flex h-8 w-8 items-center justify-center rounded border border-line bg-card text-[16px] text-ink-2 hover:bg-muted";

function Mini({ label, value, sub, color }: { label: string; value: string; sub: string; color?: string }) {
  return (
    <div className="rounded border border-line bg-card px-3 py-2">
      <div className="th" style={color ? { color } : undefined}>{label}</div>
      <div className="text-[20px] font-bold leading-6 tabular-nums text-ink">{value}</div>
      <div className="text-[11px] text-ink-3">{sub}</div>
    </div>
  );
}

/** State brief: state aggregates only. Facility detail lives in the state portal. */
export default function StateBrief({ s, month, onClose, onPrev, onNext, position }: {
  s: any; month: string; onClose: () => void; onPrev: () => void; onNext: () => void; position: string;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" && !(e.target as HTMLElement).closest("input,select")) onNext();
      if (e.key === "ArrowLeft" && !(e.target as HTMLElement).closest("input,select")) onPrev();
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [onClose, onNext, onPrev]);

  const domains = ["malaria_commodity", "vaccine_cold_chain", "service_pressure"].map((d) => ({ d, n: s[`action_${d}`] as number }));
  const maxD = Math.max(1, ...domains.map((x) => x.n));
  const trend = s.trend.map((t: any) => ({ m: t.analysis_month, act: t.act_now, vta: t.verify_then_act, ver: t.verification }));
  const first = s.trend[0], last = s.trend[s.trend.length - 1];
  const delta = first && last ? last.act_now - first.act_now : 0;
  const q = `?month=${month}`;

  return (
    <>
      <div className="fixed inset-0 z-[110] bg-black/40" onClick={onClose} aria-hidden />
      <aside role="dialog" aria-modal="true" aria-labelledby="brief-title"
        className="fixed bottom-0 right-0 top-[var(--banner-h,32px)] z-[115] flex w-full max-w-[540px] flex-col border-l border-line bg-canvas">
        <header className="border-b border-line bg-card px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="th">State brief · {s.zone} · {monthLabel(month)}</div>
              <h2 id="brief-title" className="mt-0.5 text-[22px] font-semibold leading-7 text-ink">{s.state}</h2>
              <div className="mt-1.5"><StatusChip status={s.status} /></div>
            </div>
            <div className="flex gap-1">
              <button className={iconBtn} onClick={onPrev} aria-label="Previous state" title="Previous state (←)">‹</button>
              <button className={iconBtn} onClick={onNext} aria-label="Next state" title="Next state (→)">›</button>
              <button ref={closeRef} className={iconBtn} onClick={onClose} aria-label="Close brief" title="Close (Esc)">✕</button>
            </div>
          </div>
          <p className="mt-2 text-[12px] text-ink-3">{position}</p>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Mini label="PHCs assessed" value={int(s.facilities)} sub={`${s.lgas} LGAs`} />
            <Mini label="Act now" value={int(s.act_now)} sub={`${pct(s.pct_act_now)} of PHCs`} color="var(--q-act)" />
            <Mini label="Verify then act" value={int(s.verify_then_act)} sub={pct(s.pct_verify_then_act)} color="var(--q-verify)" />
            <Mini label="Do not assume safe" value={int(s.verification)} sub={pct(s.pct_verification)} color="var(--q-dnas)" />
            <Mini label="Reporting complete" value={pct(s.reporting_completeness)} sub={`${pct(s.on_time_rate)} on time`} />
            <Mini label="Stale stock reports" value={int(s.stale_commodity)} sub={`${pct(s.pct_stale)} of PHCs`} />
          </div>

          <QueueMatrix k={s} title="Risk and confidence" />

          <section className="card p-4">
            <h3 className="mb-2 text-[14px] font-semibold text-ink">Main risk domain <span className="font-normal text-ink-3">{s.main_domain ? DOMAIN_LABEL[s.main_domain] : "none"}</span></h3>
            <div className="space-y-2.5">
              {domains.map(({ d, n }) => (
                <div key={d}>
                  <div className="mb-1 flex justify-between text-[13px]"><span className="text-ink-2">{DOMAIN_LABEL[d]}</span><b className="tabular-nums text-ink">{n}</b></div>
                  <div className="h-2 rounded-sm bg-muted"><div className="h-2 rounded-sm bg-[var(--q-act)]" style={{ width: `${(100 * n) / maxD}%`, opacity: d === s.main_domain ? 1 : 0.45 }} /></div>
                </div>
              ))}
            </div>
            <p className="mt-2 text-[12px] text-ink-3">PHCs in Resource Action, by the domain driving their risk.</p>
          </section>

          <section className="card">
            <h3 className="px-4 pt-4 text-[14px] font-semibold text-ink">Top {s.top_lgas.length} LGAs needing action <span className="font-normal text-ink-3">ranked by action, then verification</span></h3>
            <div className="overflow-x-auto p-2">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="th border-b border-line text-left">
                    <th className="px-2 py-2">LGA</th><th className="px-2 py-2 text-right">Act now</th><th className="px-2 py-2 text-right">Verify then act</th><th className="px-2 py-2 text-right">Do not assume safe</th>
                  </tr>
                </thead>
                <tbody>
                  {s.top_lgas.map((l: any) => (
                    <tr key={l.lga_id} className="border-b border-line last:border-0">
                      <td className="px-2 py-2"><Link href={`/state/${s.state_code}/lga/${l.lga_id}${q}`} className="font-medium hover:underline">{l.lga}</Link><div className="text-[11px] text-ink-3">{l.facilities} PHCs</div></td>
                      <td className="px-2 py-2 text-right tabular-nums text-act-now">{l.act_now}</td>
                      <td className="px-2 py-2 text-right tabular-nums text-verify-then-act">{l.verify_then_act}</td>
                      <td className="px-2 py-2 text-right tabular-nums text-do-not-assume-safe">{l.verification}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card p-4">
            <h3 className="mb-2 text-[14px] font-semibold text-ink">
              Last {trend.length} months <span className="font-normal text-ink-3">Act now {delta === 0 ? "unchanged" : delta > 0 ? `up ${delta}` : `down ${-delta}`} since {first ? monthLabel(first.analysis_month) : ""}</span>
            </h3>
            <ResponsiveContainer width="100%" height={170}>
              <LineChart data={trend} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="m" tickFormatter={short} {...axis} />
                <YAxis {...axis} allowDecimals={false} />
                <Tooltip {...tip} labelFormatter={(m: any) => monthLabel(m)} />
                <Legend wrapperStyle={{ fontSize: 11.5, color: "var(--ink-2)" }} iconSize={9} />
                <Line isAnimationActive={false} dataKey="act" name="Act now" stroke="var(--q-act)" strokeWidth={2} dot={{ r: 3 }} />
                <Line isAnimationActive={false} dataKey="vta" name="Verify then act" stroke="var(--q-verify)" strokeWidth={2} dot={{ r: 3 }} />
                <Line isAnimationActive={false} dataKey="ver" name="Do not assume safe" stroke="var(--q-dnas)" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="5 3" />
              </LineChart>
            </ResponsiveContainer>
          </section>
          <p className="text-[12px] text-ink-3">State-level summary only. Facility detail, queues and evidence are in the state portal.</p>
        </div>

        <footer className="border-t border-line bg-card px-5 py-3">
          <Link className="flex items-center justify-center gap-2 rounded bg-[var(--brand)] px-4 py-2 text-[13px] font-medium text-[var(--canvas)]" href={`/state/${s.state_code}${q}`}>
            Open {s.state} state portal <span aria-hidden>→</span>
          </Link>
        </footer>
      </aside>
    </>
  );
}
