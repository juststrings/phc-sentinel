"use client";
import { useState, useTransition } from "react";
import { requestStateResponse } from "@/app/actions";

export default function RequestResponse({ code, name }: { code: string; name: string }) {
  const [pending, start] = useTransition();
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  return (
    <span className="inline-flex items-center gap-2">
      <button
        className="rounded border border-line bg-card px-2.5 py-1 text-[12px] font-medium text-ink hover:bg-muted disabled:opacity-50" disabled={pending}
        onClick={() => start(async () => { const r = await requestStateResponse(code); setNote(r.ok ? { ok: true, text: `Requested from ${name}.` } : { ok: false, text: r.error }); })}
      >Request response</button>
      {note && <span role="status" className={`text-[12px] ${note.ok ? "text-monitor" : "text-act-now"}`}>{note.text}</span>}
    </span>
  );
}
