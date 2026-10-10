"use client";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { QueueTag, SimChip, StatusPill } from "@/components/Tags";
import { DOMAIN_LABEL, STATUS_STYLE, TAG_STYLE, int, lgaHref, monthLabel, pct, stateHref } from "@/lib/api";

const short = (m: string) => {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo - 1, 1).toLocaleString("en-GB", { month: "short" });
};
const axis = { stroke: "var(--axis)", tick: { fill: "var(--text-muted)", fontSize: 11 }, tickLine: false };
const tip = {
  contentStyle: { background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12, color: "var(--text-primary)" },
  labelStyle: { color: "var(--text-secondary)", fontWeight: 600 },
};

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
  const st = STATUS_STYLE[s.status];
  const trend = s.trend.map((t: any) => ({ m: t.analysis_month, act: t.act_now, vta: t.verify_then_act, ver: t.verification }));
  const first = s.trend[0], last = s.trend[s.trend.length - 1];
  const delta = first && last ? last.act_now - first.act_now : 0;

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="brief-title">
        <header>
          <div className="row">
            <div>
              <div className="eyebrow">State brief · {s.zone} · {monthLabel(month)}</div>
              <h2 id="brief-title">{s.state}</h2>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <StatusPill status={s.status} />
                <SimChip />
              </div>
            </div>
            <div style={{ display: "flex", gap: 4 }}>
              <button className="btn icon ghost" onClick={onPrev} aria-label="Previous state" title="Previous state (←)">‹</button>
              <button className="btn icon ghost" onClick={onNext} aria-label="Next state" title="Next state (→)">›</button>
              <button ref={closeRef} className="btn icon ghost" onClick={onClose} aria-label="Close brief" title="Close (Esc)">✕</button>
            </div>
          </div>
          {st && <p className="muted" style={{ margin: "8px 0 0", fontSize: 12.5 }}>{st.long}. {position}</p>}
        </header>

        <div className="body">
          <div className="mini-kpis">
            <div><span>PHCs assessed</span><b>{int(s.facilities)}</b><em>{s.lgas} LGAs</em></div>
            <div><span><i aria-hidden style={{ color: TAG_STYLE["ACT NOW"].color, fontStyle: "normal", fontSize: 10 }}>▲</i>Act now</span><b>{int(s.act_now)}</b><em>{pct(s.pct_act_now)} of PHCs</em></div>
            <div><span><i aria-hidden style={{ color: TAG_STYLE["VERIFY THEN ACT"].color, fontStyle: "normal", fontSize: 10 }}>◆</i>Verify then act</span><b>{int(s.verify_then_act)}</b><em>{pct(s.pct_verify_then_act)}</em></div>
            <div><span><i aria-hidden style={{ color: TAG_STYLE["DO NOT ASSUME SAFE"].color, fontStyle: "normal", fontSize: 10 }}>?</i>Do not assume safe</span><b>{int(s.verification)}</b><em>{pct(s.pct_verification)}</em></div>
            <div><span>Reporting complete</span><b>{pct(s.reporting_completeness)}</b><em>{pct(s.on_time_rate)} on time</em></div>
            <div><span>Stale stock reports</span><b>{int(s.stale_commodity)}</b><em>{pct(s.pct_stale)} of PHCs</em></div>
          </div>

          <div className="brief-sec">
            <h3>Risk × confidence <small>PHCs per quadrant</small></h3>
            <div className="matrix compact">
              <div />
              <div className="h">High / moderate confidence</div>
              <div className="h">Low confidence</div>
              <div className="h">High / critical risk</div>
              <div className="cell"><div className="big num">{int(s.act_now)}</div><QueueTag tag="ACT NOW" /></div>
              <div className="cell"><div className="big num">{int(s.verify_then_act)}</div><QueueTag tag="VERIFY THEN ACT" /></div>
              <div className="h">Normal / watch risk</div>
              <div className="cell"><div className="big num">{int(s.monitor)}</div><QueueTag tag="MONITOR" /></div>
              <div className="cell"><div className="big num">{int(s.verification)}</div><QueueTag tag="DO NOT ASSUME SAFE" /></div>
            </div>
          </div>

          <div className="brief-sec">
            <h3>Main risk domain <small>{s.main_domain ? DOMAIN_LABEL[s.main_domain] : "none"}</small></h3>
            {domains.map(({ d, n }) => (
              <div className="domain-row" key={d}>
                <span>{DOMAIN_LABEL[d]}</span>
                <span className="track"><i style={{ width: `${(100 * n) / maxD}%`, opacity: d === s.main_domain ? 1 : 0.45 }} /></span>
                <b>{n}</b>
              </div>
            ))}
            <p className="note" style={{ marginTop: 6 }}>PHCs in Resource Action, by the domain driving their risk.</p>
          </div>

          <div className="brief-sec">
            <h3>Top {s.top_lgas.length} LGAs needing action <small>ranked by action, then verification</small></h3>
            <table className="data">
              <thead><tr><th>LGA</th><th className="n">Act now</th><th className="n">Verify then act</th><th className="n">Do not assume safe</th></tr></thead>
              <tbody>
                {s.top_lgas.map((l: any) => (
                  <tr key={l.lga_id}>
                    <td><Link href={lgaHref(s.state_code, l.lga_id, month)}>{l.lga}</Link><div className="muted" style={{ fontSize: 11.5 }}>{l.facilities} PHCs</div></td>
                    <td className="n">{l.act_now}</td><td className="n">{l.verify_then_act}</td><td className="n">{l.verification}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="brief-sec">
            <h3>Last {trend.length} months <small>Act now {delta === 0 ? "unchanged" : delta > 0 ? `up ${delta}` : `down ${-delta}`} since {first ? monthLabel(first.analysis_month) : ""}</small></h3>
            <ResponsiveContainer width="100%" height={170}>
              <LineChart data={trend} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="m" tickFormatter={short} {...axis} />
                <YAxis {...axis} allowDecimals={false} />
                <Tooltip {...tip} labelFormatter={(m: any) => monthLabel(m)} />
                <Legend wrapperStyle={{ fontSize: 11.5, color: "var(--text-secondary)" }} iconSize={9} />
                <Line isAnimationActive={false} dataKey="act" name="Act now" stroke="var(--st-critical)" strokeWidth={2} dot={{ r: 3 }} />
                <Line isAnimationActive={false} dataKey="vta" name="Verify then act" stroke="var(--st-serious)" strokeWidth={2} dot={{ r: 3 }} />
                <Line isAnimationActive={false} dataKey="ver" name="Do not assume safe" stroke="var(--st-warning)" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="5 3" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="note">State-level summary only. Facility detail, queues and evidence are in the state portal.</p>
        </div>

        <footer>
          <Link className="btn primary" href={stateHref(s.state_code, month)}>Open {s.state} state portal <span aria-hidden>→</span></Link>
        </footer>
      </aside>
    </>
  );
}
