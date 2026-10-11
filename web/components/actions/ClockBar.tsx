"use client";
import { useState, useTransition } from "react";
import { resetSimulation, tickClock } from "@/app/actions";
import { monthLabel } from "@/lib/format";

/** The simulated date. Cases, deadlines and escalations run on it, so advancing it shows what happens when people do not act. */
export default function ClockBar({ clock, canReset }: { clock: { sim_date: string; started: string }; canReset: boolean }) {
  const [pending, start] = useTransition();
  const [err, setErr] = useState<string | null>(null);
  const run = (fn: () => Promise<{ ok: boolean; error?: string } | any>) => start(async () => { const r = await fn(); setErr(r && r.ok === false ? r.error : null); });
  const btn = "rounded border border-line bg-card px-2 py-1 text-[12px] font-medium text-ink hover:bg-muted disabled:opacity-50";
  const d = new Date(clock.sim_date + "T00:00:00");
  return (
    <div className="flex flex-wrap items-center gap-2 text-[12px] text-ink-2" aria-label="Simulated clock">
      <span className="th">Simulated date</span>
      <b className="text-[13px] text-ink">{d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</b>
      <button className={btn} disabled={pending} onClick={() => run(() => tickClock(1))}>+1 day</button>
      <button className={btn} disabled={pending} onClick={() => run(() => tickClock(7))}>+7 days</button>
      {canReset && <button className={btn} disabled={pending} onClick={() => { if (confirm("Reset the simulation to a clean start? Cases, messages and replies go back to the seeded state.")) run(resetSimulation); }}>Reset</button>}
      {pending && <span className="text-ink-3">working…</span>}
      {err && <span role="alert" className="text-act-now">{err}</span>}
    </div>
  );
}
