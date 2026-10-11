"use client";
import Link from "next/link";
import { useState, useTransition } from "react";
import { reviewResponse } from "@/app/actions";
import { Pill } from "./ui";

/** Replies that came back (simulated). A parser reads "ACT 40 RDT 12 FRIDGE 1"; anything unclear waits for a person to review. */
export default function Replies({ responses }: { responses: any[] }) {
  const [pending, start] = useTransition();
  const [fix, setFix] = useState<{ id: string; text: string } | null>(null);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const run = (id: string, opts: { corrected_text?: string; dismiss?: boolean }) => start(async () => {
    const r = await reviewResponse(id, opts);
    setNote(r.ok ? { ok: true, text: "Reviewed." } : { ok: false, text: r.error });
    if (r.ok) setFix(null);
  });
  const btn = "rounded border border-line bg-card px-2.5 py-1 text-[12px] font-medium text-ink hover:bg-muted disabled:opacity-50";
  if (responses.length === 0) return <p className="px-4 py-8 text-center text-ink-3">No replies yet. Approve messages, then advance the simulated clock to see replies arrive.</p>;
  return (
    <ul>
      {note && <li role="status" className={`border-b border-line px-4 py-2 text-[12px] ${note.ok ? "text-monitor" : "text-act-now"}`}>{note.text}</li>}
      {responses.map((r) => (
        <li key={r.response_id} className="border-b border-line px-4 py-3 text-[13px] last:border-0">
          <div className="flex flex-wrap items-center gap-2">
            <b className="text-ink">{r.from_name}</b>
            <Pill t={r.parse_status === "parsed" ? "ok" : r.parse_status === "unparseable" ? "act" : "verify"}>{r.parse_status}</Pill>
            <Pill t={r.review_status === "needs_review" ? "verify" : "plain"}>{(r.review_status ?? "").replace(/_/g, " ")}</Pill>
            {r.case_id && <Link href={`/cases/${r.case_id}`} className="text-[12px] text-ink-2 underline-offset-2 hover:underline">{r.case_ref}{r.unit_name ? ` · ${r.unit_name}` : ""}</Link>}
            <span className="text-[11px] text-ink-3">{String(r.received_at).slice(0, 10)}</span>
          </div>
          <p className="mt-1 rounded border border-line bg-muted px-2.5 py-1.5 text-ink-2">{r.raw_text}</p>
          {r.parsed && <p className="mt-1 text-[12px] text-ink-3">Read as: {JSON.stringify(r.parsed)}</p>}
          {r.review_status === "needs_review" && (
            fix?.id === r.response_id ? (
              <div className="mt-2 space-y-2">
                <input value={fix?.text ?? ""} onChange={(e) => setFix({ id: fix!.id, text: e.target.value })} className="w-full rounded border border-line bg-card p-2 text-[13px] text-ink" aria-label="Corrected reply" />
                <div className="flex gap-2"><button className={btn} disabled={pending} onClick={() => run(r.response_id, { corrected_text: fix!.text })}>Apply corrected reply</button><button className={btn} onClick={() => setFix(null)}>Cancel</button></div>
              </div>
            ) : (
              <div className="mt-2 flex gap-2">
                <button className={btn} onClick={() => setFix({ id: r.response_id, text: r.raw_text })}>Correct and apply</button>
                <button className={btn} disabled={pending} onClick={() => run(r.response_id, { dismiss: true })}>Dismiss</button>
              </div>
            )
          )}
        </li>
      ))}
    </ul>
  );
}
