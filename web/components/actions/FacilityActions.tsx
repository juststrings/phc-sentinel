"use client";
import Link from "next/link";
import { useState, useTransition } from "react";
import { openFacilityCase } from "@/app/actions";
import { CaseStatusPill, Pill, PriorityPill, pretty } from "./ui";

/** On a facility page: live status next to the monthly baseline, the cases already open for it, and what to start. */
export default function FacilityActions({ code, facilityId, data }: { code: string; facilityId: string; data: any }) {
  const [pending, start] = useTransition();
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const [other, setOther] = useState(data.playbooks[0]?.playbook ?? "");
  const lv = data.live;
  const open = data.cases.filter((c: any) => !["resolved", "closed_no_action", "closed_duplicate"].includes(c.status));
  const startCase = (playbook?: string, ruleId?: string) => start(async () => {
    const r = await openFacilityCase(code, facilityId, playbook, ruleId);
    setNote(r.ok ? { ok: true, text: "Case opened: see it in the Action Centre." } : { ok: false, text: r.error });
  });
  const btn = "rounded border border-line bg-card px-2.5 py-1 text-[12px] font-medium text-ink hover:bg-muted disabled:opacity-50";
  return (
    <section className="card p-4" aria-label="Take action">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[16px] font-semibold text-ink">Take action</h2>
        <span className="text-[12px] text-ink-3">Simulated clock: {data.clock.sim_date}</span>
      </div>
      <div className="mt-3 grid gap-4 md:grid-cols-3">
        <div>
          <div className="th mb-1">Status now</div>
          <p className="text-[13px] text-ink-2">Monthly assessment: <b className="text-ink">{lv.baseline_tag}</b></p>
          <p className="text-[13px] text-ink-2">Live: <b className="text-ink">{lv.live_tag}</b>{lv.field_verified ? " (field verified)" : ""}</p>
          {lv.changed && <p className="mt-1 text-[12px] text-monitor">A field count changed this facility&apos;s status.</p>}
        </div>
        <div>
          <div className="th mb-1">Open cases</div>
          {open.length === 0 ? <p className="text-[13px] text-ink-3">None.</p> : (
            <ul className="space-y-1.5">
              {open.map((c: any) => (
                <li key={c.case_id} className="text-[13px]">
                  <Link href={`/cases/${c.case_id}`} className="font-medium hover:underline">{c.case_ref}</Link> <PriorityPill p={c.priority} /> <CaseStatusPill status={c.status} />
                  <div className="text-[11px] text-ink-3">{pretty(c.rule_id?.replace(/^R\d+_/, ""))} · owner {c.owner_name ?? "unassigned"}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <div className="th mb-1">Start a case</div>
          {data.recommended.length > 0 && (
            <ul className="mb-2 space-y-1.5">
              {data.recommended.map((r: any) => (
                <li key={r.rule_id} className="flex items-center justify-between gap-2 text-[13px]">
                  <span className="min-w-0 text-ink-2">{r.title} <PriorityPill p={r.priority} /><span className="block text-[11px] text-ink-3">for {r.owner_title}</span></span>
                  <button className={btn} disabled={pending} onClick={() => startCase(r.playbook, r.rule_id)}>Open</button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <select className="min-w-0 flex-1 rounded border border-line bg-card px-2 py-1 text-[12px] text-ink" value={other} onChange={(e) => setOther(e.target.value)} aria-label="Playbook">
              {data.playbooks.map((p: any) => <option key={p.playbook} value={p.playbook}>{p.title}</option>)}
            </select>
            <button className={btn} disabled={pending || !other} onClick={() => startCase(other)}>Open</button>
          </div>
        </div>
      </div>
      {note && <p role="status" className={`mt-2 text-[12px] ${note.ok ? "text-monitor" : "text-act-now"}`}>{note.text}</p>}
      <p className="mt-2 text-[11px] text-ink-3"><Pill>Simulated</Pill> Cases are opened as the person chosen in Acting as (set it in the Action Centre).</p>
    </section>
  );
}
