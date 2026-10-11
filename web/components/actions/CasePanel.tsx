"use client";
import { useState, useTransition } from "react";
import { caseAction, sendReply } from "@/app/actions";

/** What you can do to one case, as the acting person: acknowledge, assign, advance the playbook, resolve or close, add a note,
 *  and (for facility staff) reply to a message. The API refuses anything outside the person's scope and the screen shows why. */
export default function CasePanel({ caseId, status, owner, people, outcomes, actingLevel, hasExpectingMessage }: {
  caseId: string; status: string; owner: string | null; people: { person_id: string; name: string; role_title: string }[];
  outcomes: Record<string, string>; actingLevel: string; hasExpectingMessage: boolean;
}) {
  const [pending, start] = useTransition();
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const [assignTo, setAssignTo] = useState(people[0]?.person_id ?? "");
  const [outcome, setOutcome] = useState(Object.keys(outcomes)[0] ?? "");
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const closed = ["resolved", "closed_no_action", "closed_duplicate"].includes(status);
  const run = (fn: () => Promise<{ ok: boolean; error?: string }>, done: string) => start(async () => {
    const r = await fn();
    setNote(r.ok ? { ok: true, text: done } : { ok: false, text: (r as any).error });
  });
  const btn = "rounded border border-line bg-card px-2.5 py-1.5 text-[13px] font-medium text-ink hover:bg-muted disabled:opacity-50";
  const sel = "w-full rounded border border-line bg-card px-2 py-1.5 text-[13px] text-ink";

  return (
    <section className="card space-y-4 p-4" aria-label="Case actions">
      <h2 className="text-[16px] font-semibold text-ink">Take action</h2>
      {closed ? <p className="text-[13px] text-ink-3">This case is {status.replace(/_/g, " ")}.</p> : (
        <>
          <div className="flex flex-wrap gap-2">
            <button className={btn} disabled={pending} onClick={() => run(() => caseAction(caseId, "acknowledge"), "Acknowledged.")}>Acknowledge</button>
            <button className={btn} disabled={pending} onClick={() => run(() => caseAction(caseId, "advance"), "Moved to the next playbook step.")}>Next step</button>
          </div>
          <div>
            <label className="mb-1 block text-[11px] text-ink-3">Assign to {owner ? `(now ${owner})` : ""}</label>
            <div className="flex gap-2">
              <select className={sel} value={assignTo} onChange={(e) => setAssignTo(e.target.value)} aria-label="Assign to">
                {people.map((p) => <option key={p.person_id} value={p.person_id}>{p.name}: {p.role_title}</option>)}
              </select>
              <button className={btn} disabled={pending || !assignTo} onClick={() => run(() => caseAction(caseId, "assign", { person_id: assignTo }), "Assigned.")}>Assign</button>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[11px] text-ink-3">Outcome</label>
            <div className="flex gap-2">
              <select className={sel} value={outcome} onChange={(e) => setOutcome(e.target.value)} aria-label="Outcome">
                {Object.entries(outcomes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <button className={btn} disabled={pending} onClick={() => run(() => caseAction(caseId, "resolve", { outcome_code: outcome, note: text || undefined }), "Resolved.")}>Resolve</button>
              <button className={btn} disabled={pending} onClick={() => run(() => caseAction(caseId, "close", { outcome_code: outcome, note: text || undefined }), "Closed.")}>Close</button>
            </div>
          </div>
        </>
      )}
      <div>
        <label className="mb-1 block text-[11px] text-ink-3">Note</label>
        <textarea rows={2} className={sel} value={text} onChange={(e) => setText(e.target.value)} aria-label="Note" placeholder="What was done, or what is needed" />
        <button className={`${btn} mt-2`} disabled={pending || !text.trim()} onClick={() => run(async () => { const r = await caseAction(caseId, "note", { text }); if (r.ok) setText(""); return r; }, "Note added.")}>Add note</button>
      </div>
      {actingLevel === "facility" && hasExpectingMessage && !closed && (
        <div>
          <label className="mb-1 block text-[11px] text-ink-3">Reply to the message (as facility staff, like an SMS)</label>
          <div className="flex gap-2">
            <input className={sel} value={reply} onChange={(e) => setReply(e.target.value)} aria-label="Reply" placeholder="ACT 40 RDT 12 FRIDGE 1" />
            <button className={btn} disabled={pending || !reply.trim()} onClick={() => run(async () => { const r = await sendReply(caseId, reply); if (r.ok) setReply(""); return r; }, "Reply recorded and read.")}>Send reply</button>
          </div>
        </div>
      )}
      {note && <p role="status" className={`text-[12px] ${note.ok ? "text-monitor" : "text-act-now"}`}>{note.text}</p>}
    </section>
  );
}
