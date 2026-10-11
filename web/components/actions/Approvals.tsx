"use client";
import Link from "next/link";
import { useState, useTransition } from "react";
import { approveMessages, editMessage } from "@/app/actions";
import { PriorityPill, Pill } from "./ui";

/** Messages drafted from templates. Every one waits here for a person to approve it; "sending" is simulated. */
export default function Approvals({ messages, total }: { messages: any[]; total: number }) {
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [edit, setEdit] = useState<{ id: string; text: string } | null>(null);
  const [pending, start] = useTransition();
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const drafts = messages.filter((m) => m.status === "draft");
  const toggle = (id: string) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const approve = (ids: string[]) => start(async () => {
    const r = await approveMessages(ids);
    setNote(r.ok ? { ok: true, text: `${ids.length} approved: simulated as sent.` } : { ok: false, text: r.error });
    if (r.ok) setSel(new Set());
  });
  const save = () => edit && start(async () => {
    const r = await editMessage(edit.id, edit.text);
    setNote(r.ok ? { ok: true, text: "Message updated." } : { ok: false, text: r.error });
    if (r.ok) setEdit(null);
  });
  const btn = "rounded border border-line bg-card px-2.5 py-1 text-[12px] font-medium text-ink hover:bg-muted disabled:opacity-50";

  return (
    <div>
      <div className="flex min-h-[44px] flex-wrap items-center gap-2 border-b border-line px-4 py-2 text-[12px] text-ink-2">
        <b className="text-ink">{total.toLocaleString()} message{total === 1 ? "" : "s"}</b>
        <span>· showing the first {messages.length}. Each is a DEMO draft: approving marks it as simulated sent.</span>
        {drafts.length > 0 && (
          <>
            <button className={`${btn} ml-auto`} disabled={pending || sel.size === 0} onClick={() => approve([...sel])}>Approve selected ({sel.size})</button>
            <button className={btn} disabled={pending} onClick={() => setSel(new Set(drafts.map((m) => m.message_id)))}>Select all shown</button>
          </>
        )}
        {note && <span role="status" className={note.ok ? "text-monitor" : "text-act-now"}>{note.text}</span>}
      </div>
      {messages.length === 0 ? <p className="px-4 py-8 text-center text-ink-3">No messages.</p> : (
        <ul>
          {messages.map((m) => (
            <li key={m.message_id} className="flex gap-3 border-b border-line px-4 py-3 last:border-0">
              {m.status === "draft" ? <input className="mt-1" type="checkbox" aria-label={`Select ${m.message_id}`} checked={sel.has(m.message_id)} onChange={() => toggle(m.message_id)} /> : <span className="w-4" />}
              <div className="min-w-0 flex-1 text-[13px]">
                <div className="flex flex-wrap items-center gap-2">
                  <b className="text-ink">To {m.to_name}</b><span className="text-ink-3">{m.to_role?.replace(/_/g, " ")}</span>
                  <Pill>{m.channel}</Pill><PriorityPill p={m.priority} />
                  <Pill t={m.status === "draft" ? "verify" : m.status === "replied" ? "ok" : "plain"}>{m.status.replace(/_/g, " ")}</Pill>
                  {m.case_id && <Link href={`/cases/${m.case_id}`} className="text-[12px] text-ink-2 underline-offset-2 hover:underline">{m.case_ref}{m.unit_name ? ` · ${m.unit_name}` : ""}</Link>}
                </div>
                {edit?.id === m.message_id ? (
                  <div className="mt-2 space-y-2">
                    <textarea value={edit?.text ?? ""} onChange={(e) => setEdit({ id: edit!.id, text: e.target.value })} rows={3}
                      className="w-full rounded border border-line bg-card p-2 text-[13px] text-ink" aria-label="Message text" />
                    <div className="flex gap-2"><button className={btn} disabled={pending} onClick={save}>Save</button><button className={btn} onClick={() => setEdit(null)}>Cancel</button></div>
                  </div>
                ) : (
                  <p className="mt-1 rounded border border-line bg-muted px-2.5 py-1.5 text-ink-2">{m.body}<span className="ml-2 text-[11px] text-ink-3">{m.chars} chars · {m.phone_display ?? m.email}</span></p>
                )}
                {m.reply_text && <p className="mt-1 text-[12px] text-ink-2"><b>Reply:</b> {m.reply_text} <span className="text-ink-3">({m.reply_parse})</span></p>}
              </div>
              {m.status === "draft" && edit?.id !== m.message_id && (
                <div className="flex shrink-0 flex-col gap-1">
                  <button className={btn} disabled={pending} onClick={() => approve([m.message_id])}>Approve</button>
                  <button className={btn} onClick={() => setEdit({ id: m.message_id, text: m.body })}>Edit</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
