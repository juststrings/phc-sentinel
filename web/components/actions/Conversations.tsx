"use client";
import { useState, useTransition } from "react";
import { sendDirect } from "@/app/actions";
import { Pill } from "./ui";

type Msg = { message_id: string; sender_person_id: string; from_name: string; from_role: string; to_name: string; body: string; created_at: string; status: string };
export type Thread = { thread_id: string; facility_id: string | null; facility: string | null; people: { person_id: string; name: string; role_code: string }[]; messages: Msg[] };

const clean = (b: string) => b.replace(/^Sentinel \(DEMO\) from [^:]+: /, "");

/** Two-way conversations. Each bubble says who wrote it; if you are acting as someone in the conversation you can reply to the others. */
export default function Conversations({ threads, actingId, actingName, showFacility = false, empty = "No conversations yet." }:
  { threads: Thread[]; actingId: string; actingName: string; showFacility?: boolean; empty?: string }) {
  if (threads.length === 0) return <p className="px-4 py-6 text-[13px] text-ink-3">{empty}</p>;
  return <ul className="divide-y divide-line">{threads.map((t) => <ThreadRow key={t.thread_id} t={t} actingId={actingId} actingName={actingName} showFacility={showFacility} />)}</ul>;
}

function ThreadRow({ t, actingId, actingName, showFacility }: { t: Thread; actingId: string; actingName: string; showFacility: boolean }) {
  const [text, setText] = useState("");
  const [pending, start] = useTransition();
  const [err, setErr] = useState<string | null>(null);
  const others = t.people.filter((p) => p.person_id !== actingId);
  const mine = t.people.some((p) => p.person_id === actingId);
  const send = () => start(async () => {
    const r = await sendDirect(others.map((p) => p.person_id), text.trim(), { threadId: t.thread_id });
    if (r.ok) { setText(""); setErr(null); } else setErr(r.error);
  });
  return (
    <li className="px-4 py-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
        <b className="text-ink">{t.people.map((p) => p.name).join(", ")}</b>
        {showFacility && t.facility && <span>about {t.facility}</span>}
        <Pill>{t.messages.length} message{t.messages.length === 1 ? "" : "s"}</Pill>
      </div>
      <ul className="space-y-1.5">
        {t.messages.map((m) => {
          const me = m.sender_person_id === actingId;
          return (
            <li key={m.message_id} className={`flex ${me ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-lg border px-3 py-1.5 text-[13px] ${me ? "border-[var(--brand)] bg-muted" : "border-line bg-card"}`}>
                <div className="text-[11px] text-ink-3">{me ? "You" : m.from_name} · {m.from_role} · {String(m.created_at).slice(0, 10)}</div>
                <div className="text-ink">{clean(m.body)}</div>
              </div>
            </li>
          );
        })}
      </ul>
      {mine ? (
        <div className="mt-2 flex gap-2">
          <input value={text} onChange={(e) => setText(e.target.value)} maxLength={400} placeholder={`Reply as ${actingName}`} aria-label="Reply"
            className="min-w-0 flex-1 rounded border border-line bg-card px-2 py-1 text-[13px] text-ink"
            onKeyDown={(e) => { if (e.key === "Enter" && text.trim() && !pending) send(); }} />
          <button disabled={pending || !text.trim()} onClick={send}
            className="rounded bg-[var(--brand)] px-3 py-1 text-[12px] font-semibold text-[var(--canvas)] disabled:opacity-50">Reply</button>
        </div>
      ) : <p className="mt-2 text-[11px] text-ink-3">To reply, set Acting as to one of: {t.people.map((p) => p.name).join(", ")}.</p>}
      {err && <p role="alert" className="mt-1 text-[12px] text-act-now">{err}</p>}
    </li>
  );
}
