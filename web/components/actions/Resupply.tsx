"use client";
import { useState, useTransition } from "react";
import Link from "next/link";
import { approveResupply } from "@/app/actions";
import { Pill } from "./ui";

/** Resupply requests are pre-filled from the stock position but always need approval; nothing moves stock. */
export default function Resupply({ requests, code }: { requests: any[]; code: string }) {
  const [pending, start] = useTransition();
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const approve = (id: string) => start(async () => { const r = await approveResupply(id); setNote(r.ok ? { ok: true, text: "Approved (simulated)." } : { ok: false, text: r.error }); });
  const btn = "rounded border border-line bg-card px-2.5 py-1 text-[12px] font-medium text-ink hover:bg-muted disabled:opacity-50";
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-2 text-[12px] text-ink-2">
        <span>{requests.length} request{requests.length === 1 ? "" : "s"}. Synthetic: not real orders.</span>
        <a className={`${btn} ml-auto`} href={`/api/resupply?state=${code}`}>Export CSV</a>
        {note && <span role="status" className={note.ok ? "text-monitor" : "text-act-now"}>{note.text}</span>}
      </div>
      {requests.length === 0 ? <p className="px-4 py-8 text-center text-ink-3">No resupply requests.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead><tr className="th border-b border-line text-left"><th className="px-4 py-2">Facility</th><th className="px-2 py-2">LGA</th><th className="px-2 py-2">Commodity</th><th className="px-2 py-2 text-right">Quantity</th><th className="px-2 py-2">Status</th><th className="px-2 py-2" /></tr></thead>
            <tbody>
              {requests.slice(0, 100).map((r) => (
                <tr key={r.request_id} className="border-b border-line last:border-0 hover:bg-muted">
                  <td className="px-4 py-2"><Link href={`/cases/${r.case_id}`} className="font-medium hover:underline">{r.facility}</Link><div className="text-[11px] text-ink-3">{r.case_ref} · {r.ward}</div></td>
                  <td className="px-2 py-2 text-ink-2">{r.lga}</td><td className="px-2 py-2 text-ink-2">{r.commodity_code}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{Math.round(r.qty_requested).toLocaleString()}</td>
                  <td className="px-2 py-2"><Pill t={r.status === "approved" ? "ok" : "verify"}>{String(r.status).replace(/_/g, " ")}</Pill></td>
                  <td className="px-2 py-2 text-right">{r.status !== "approved" && <button className={btn} disabled={pending} onClick={() => approve(r.request_id)}>Approve</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {requests.length > 100 && <p className="px-4 py-2 text-[12px] text-ink-3">Showing the first 100; export the CSV for all {requests.length}.</p>}
        </div>
      )}
    </div>
  );
}
