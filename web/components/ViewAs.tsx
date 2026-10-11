"use client";
import { useEffect, useRef, useState } from "react";
import { COOKIE, homeOf, scopeHeader, type Scope } from "@/lib/scopeCore";

type St = { code: string; name: string; zone: string };
type Lga = { lga_id: string; lga: string };

export function scopeTitle(s: Scope, states: St[], lgaName?: string): { who: string; where: string } {
  const st = (c: string) => states.find((x) => x.code === c)?.name ?? c;
  if (s.level === "national") return { who: "National admin", where: "All states" };
  if (s.level === "state") return { who: "State board", where: st(s.state) };
  return { who: "LGA team", where: `${lgaName ?? s.lga}, ${st(s.state)}` };
}

const field = "w-full rounded border border-line bg-card px-2 py-1.5 text-[13px] text-ink";

/** Power BI-style "View as": pick who you are looking at the dashboard as. The choice is a cookie the API turns into a
 *  row-level filter, so a state or LGA view only ever receives its own rows. Demo-grade: anyone can switch. */
export default function ViewAs({ scope, states, lgaName }: { scope: Scope; states: St[]; lgaName?: string }) {
  const [open, setOpen] = useState(false);
  const [level, setLevel] = useState<Scope["level"]>(scope.level);
  const [state, setState] = useState(scope.level === "national" ? states[0]?.code ?? "" : scope.state);
  const [lga, setLga] = useState(scope.level === "lga" ? scope.lga : "");
  const [lgas, setLgas] = useState<Lga[]>([]);
  const box = useRef<HTMLDivElement>(null);
  const now = scopeTitle(scope, states, lgaName);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  useEffect(() => {
    if (level !== "lga" || !state) return;
    let live = true;
    fetch(`/api/lgas?state=${encodeURIComponent(state)}`).then((r) => r.json()).then((rows: Lga[]) => {
      if (!live) return;
      setLgas(rows);
      setLga((cur) => (rows.some((l) => l.lga_id === cur) ? cur : rows[0]?.lga_id ?? ""));
    }).catch(() => setLgas([]));
    return () => { live = false; };
  }, [level, state]);

  const next: Scope | null = level === "national" ? { level: "national" }
    : level === "state" ? (state ? { level: "state", state } : null)
    : state && lga ? { level: "lga", state, lga } : null;

  const apply = () => {
    if (!next) return;
    const maxAge = 60 * 60 * 24 * 365;
    document.cookie = `${COOKIE}=${encodeURIComponent(scopeHeader(next))}; path=/; max-age=${maxAge}; samesite=lax`;
    document.cookie = `phc_acting=; path=/; max-age=0`;                 // the acting person belongs to the old view
    window.location.assign(homeOf(next));                               // full load: every server component re-reads the cookie
  };

  const radio = (v: Scope["level"], label: string, hint: string) => (
    <label className={`flex cursor-pointer items-start gap-2 rounded border px-2.5 py-2 text-[13px] ${level === v ? "border-[var(--brand)] bg-muted" : "border-line hover:bg-muted"}`}>
      <input type="radio" name="view-level" checked={level === v} onChange={() => setLevel(v)} className="mt-0.5" />
      <span><span className="font-medium text-ink">{label}</span><span className="block text-[11px] text-ink-3">{hint}</span></span>
    </label>
  );

  return (
    <div ref={box} className="relative px-3 pb-3 shell-chrome">
      <span className="th mb-1 block">Viewing as</span>
      <button
        type="button" onClick={() => setOpen((o) => !o)} aria-haspopup="dialog" aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 rounded border border-line bg-card px-2.5 py-2 text-left hover:bg-muted"
      >
        <span className="min-w-0">
          <span className="block truncate text-[13px] font-semibold text-ink">{now.who}</span>
          <span className="block truncate text-[11px] text-ink-3">{now.where}</span>
        </span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden><path d="m6 9 6 6 6-6" /></svg>
      </button>
      {open && (
        <div role="dialog" aria-label="View as" className="absolute left-3 right-3 z-[60] mt-1 space-y-2 rounded-lg border border-line bg-card p-3 shadow-lg md:right-auto md:w-[260px]">
          <div className="space-y-1.5">
            {radio("national", "National admin", "Everything, in every state")}
            {radio("state", "State board", "One state and its LGAs")}
            {radio("lga", "LGA team", "One LGA and its clinics")}
          </div>
          {level !== "national" && (
            <label className="block text-[11px] text-ink-3">State
              <select className={`${field} mt-0.5`} value={state} onChange={(e) => setState(e.target.value)}>
                {states.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
              </select>
            </label>
          )}
          {level === "lga" && (
            <label className="block text-[11px] text-ink-3">LGA
              <select className={`${field} mt-0.5`} value={lga} onChange={(e) => setLga(e.target.value)}>
                {lgas.map((l) => <option key={l.lga_id} value={l.lga_id}>{l.lga}</option>)}
              </select>
            </label>
          )}
          <button
            type="button" onClick={apply} disabled={!next}
            className="w-full rounded bg-[var(--brand)] px-3 py-1.5 text-[13px] font-medium text-[var(--canvas)] disabled:opacity-50"
          >View as this</button>
          <p className="text-[11px] leading-4 text-ink-3">
            Demo: this is a filter, not a login. The API returns only the rows this view may see.
          </p>
        </div>
      )}
    </div>
  );
}
