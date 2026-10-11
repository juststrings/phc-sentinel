"use client";
import Link from "next/link";
import { useState, useTransition } from "react";
import { bulkAction } from "@/app/actions";
import { CaseStatusPill, PriorityPill, pretty } from "./ui";

/** Cases as a table with selection and bulk actions (acknowledge, approve messages). Opens a case on click. */
export default function CaseList({ cases, today, showLga }: { cases: any[]; today: string; showLga: boolean }) {
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [pending, start] = useTransition();
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const all = cases.length > 0 && cases.every((c) => sel.has(c.case_id));
  const toggle = (id: string) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const run = (action: string) => start(async () => {
    const r = await bulkAction({ action, case_ids: [...sel] });
    setNote(r.ok ? { ok: true, text: `Done for ${sel.size} case${sel.size === 1 ? "" : "s"}.` } : { ok: false, text: r.error });
    if (r.ok) setSel(new Set());
  });
  const btn = "rounded border border-line bg-card px-2.5 py-1 text-[12px] font-medium text-ink hover:bg-muted disabled:opacity-50";

  if (cases.length === 0) return <p className="px-4 py-8 text-center text-ink-3">No cases match these filters.</p>;
  return (
    <div>
      <div className="flex min-h-[44px] flex-wrap items-center gap-2 border-b border-line px-4 py-2 text-[12px] text-ink-2">
        {sel.size === 0 ? <span>Select cases to act on several at once.</span> : (
          <>
            <b className="text-ink">{sel.size} selected</b>
            <button className={btn} disabled={pending} onClick={() => run("acknowledge")}>Acknowledge</button>
            <button className={btn} disabled={pending} onClick={() => run("approve_messages")}>Approve their messages</button>
            <button className={btn} onClick={() => setSel(new Set())}>Clear</button>
          </>
        )}
        {note && <span role="status" className={note.ok ? "text-monitor" : "text-act-now"}>{note.text}</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="th border-b border-line text-left">
              <th className="px-4 py-2"><input type="checkbox" aria-label="Select all" checked={all} onChange={() => setSel(all ? new Set() : new Set(cases.map((c) => c.case_id)))} /></th>
              <th className="px-2 py-2">Case</th><th className="px-2 py-2">Priority</th><th className="px-2 py-2">Status</th>
              <th className="px-2 py-2">Owner</th><th className="px-2 py-2">Due</th><th className="px-2 py-2">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => {
              const overdue = c.due_at < today && !["resolved", "closed_no_action", "closed_duplicate"].includes(c.status);
              return (
                <tr key={c.case_id} className="border-b border-line align-top last:border-0 hover:bg-muted">
                  <td className="px-4 py-2.5"><input type="checkbox" aria-label={`Select ${c.case_ref}`} checked={sel.has(c.case_id)} onChange={() => toggle(c.case_id)} /></td>
                  <td className="px-2 py-2.5">
                    <Link href={`/cases/${c.case_id}`} className="font-medium hover:underline">{c.unit_name ?? c.case_ref}</Link>
                    <div className="text-[11px] text-ink-3">{c.case_ref} · {pretty(c.rule_id?.replace(/^R\d+_/, ""))}{showLga && c.lga ? ` · ${c.lga}` : ""}</div>
                  </td>
                  <td className="px-2 py-2.5"><PriorityPill p={c.priority} /></td>
                  <td className="px-2 py-2.5">
                    <CaseStatusPill status={c.status} overdue={overdue} />
                    {c.escalation_level > 0 && <div className="mt-1 text-[11px] text-act-now">Escalated to {c.escalated_to_name ?? c.escalated_to_role}</div>}
                    {c.acknowledged_at == null && !overdue && <div className="mt-1 text-[11px] text-ink-3">Not acknowledged</div>}
                  </td>
                  <td className="px-2 py-2.5 text-ink-2">{c.owner_name ?? "Unassigned"}<div className="text-[11px] text-ink-3">{c.owner_role_title}</div></td>
                  <td className="whitespace-nowrap px-2 py-2.5 tabular-nums text-ink-2">{c.due_at}</td>
                  <td className="max-w-[320px] px-2 py-2.5 text-ink-2">{c.evidence_summary}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
