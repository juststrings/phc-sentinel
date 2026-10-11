"use client";
import { useState, useTransition } from "react";
import { sendDirect } from "@/app/actions";
import Conversations, { type Thread } from "./Conversations";
import { Pill } from "./ui";

const QUICK = [
  "Please confirm your current ACT and RDT stock today.",
  "Please check that the vaccine fridge is working and tell us.",
  "Please submit the monthly report as soon as you can.",
];

/** On a facility page: who is in charge (facility, LGA, state), write to them, and read the replies. */
export default function PeopleInCharge({ facilityId, facilityName, data, threads, acting, actingPicker }:
  { facilityId: string; facilityName: string; data: any; threads: Thread[]; acting: { person_id: string; name: string; role_title?: string }; actingPicker?: React.ReactNode }) {
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [text, setText] = useState("");
  const [pending, start] = useTransition();
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const toggle = (id: string) => setPicked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const tierPeople = (t: any) => t.people.filter((p: any) => p.person_id !== acting.person_id);
  const send = () => start(async () => {
    const r = await sendDirect([...picked], text.trim(), { facilityId });
    if (r.ok) { setNote({ ok: true, text: `Sent (simulated) to ${picked.size} ${picked.size === 1 ? "person" : "people"}.` }); setText(""); setPicked(new Set()); }
    else setNote({ ok: false, text: r.error });
  });
  return (
    <section className="card p-4" aria-label="People in charge">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[16px] font-semibold text-ink">People in charge</h2>
        {actingPicker ?? <span className="text-[12px] text-ink-3">Writing as <b className="text-ink">{acting.name}</b></span>}
      </div>
      <div className="mt-3 grid gap-4 lg:grid-cols-12">
        <div className="space-y-3 lg:col-span-5">
          {data.tiers.map((t: any) => (
            <div key={t.tier}>
              <div className="th mb-1">{t.title}</div>
              {tierPeople(t).length === 0 ? <p className="text-[13px] text-ink-3">Nobody listed.</p> : (
                <ul className="space-y-1">
                  {tierPeople(t).map((p: any) => (
                    <li key={p.person_id}>
                      <label className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 text-[13px] hover:bg-muted">
                        <input type="checkbox" className="mt-1" checked={picked.has(p.person_id)} onChange={() => toggle(p.person_id)} />
                        <span><b className="text-ink">{p.name}</b> <span className="text-ink-3">{p.role_title}</span>
                          <span className="block text-[11px] text-ink-3">{p.preferred_channel === "sms" ? `${p.phone_display} · ` : ""}by {p.preferred_channel}</span></span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
        <div className="lg:col-span-7">
          <div className="th mb-1">Message to {picked.size ? `${picked.size} selected` : "the people you tick"}, about {facilityName}</div>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={400} aria-label="Message"
            className="w-full rounded border border-line bg-card px-2 py-1.5 text-[13px] text-ink" placeholder="Write a message…" />
          <div className="mt-1 flex flex-wrap gap-1.5">
            {QUICK.map((q) => <button key={q} type="button" onClick={() => setText(q)} className="rounded-full border border-line px-2 py-0.5 text-[11px] text-ink-2 hover:bg-muted">{q.split(" ").slice(1, 6).join(" ")}…</button>)}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <button disabled={pending || picked.size === 0 || !text.trim()} onClick={send}
              className="rounded bg-[var(--brand)] px-3 py-1.5 text-[13px] font-semibold text-[var(--canvas)] disabled:opacity-50">Send (simulated)</button>
            <Pill>Simulated</Pill><span className="text-[11px] text-ink-3">Nothing is sent. Replies come back as the simulated clock moves.</span>
          </div>
          {note && <p role="status" className={`mt-1 text-[12px] ${note.ok ? "text-monitor" : "text-act-now"}`}>{note.text}</p>}
        </div>
      </div>
      <div className="mt-4 border-t border-line pt-3">
        <div className="th mb-1">Conversations about this facility</div>
        <div className="-mx-4">
          <Conversations threads={threads} actingId={acting.person_id} actingName={acting.name} empty="No messages about this facility yet." />
        </div>
      </div>
    </section>
  );
}
