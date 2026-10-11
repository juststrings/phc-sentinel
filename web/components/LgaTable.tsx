"use client";
import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { pct } from "@/lib/format";
import { QUEUE_CLASS, queueStyle } from "@/lib/tokens";

const SEGMENTS = [
  { key: "act_now", tag: "ACT NOW" },
  { key: "verify_then_act", tag: "VERIFY THEN ACT" },
  { key: "verification", tag: "DO NOT ASSUME SAFE" },
  { key: "monitor", tag: "MONITOR" },
] as const;

function Bar({ row }: { row: any }) {
  const total = row.facilities || 1;
  const title = SEGMENTS.map((s) => `${queueStyle(s.tag).label}: ${row[s.key]}`).join(", ");
  return (
    <div className="flex h-2.5 w-full min-w-[56px] overflow-hidden rounded-sm bg-muted" title={title} role="img" aria-label={title}>
      {SEGMENTS.map((s) => {
        const w = (row[s.key] / total) * 100;
        return w > 0 ? <div key={s.key} className={QUEUE_CLASS[queueStyle(s.tag).token].bar} style={{ width: `${w}%` }} /> : null;
      })}
    </div>
  );
}

function Table({ rows, month, code, sticky, fill }: { rows: any[]; month: string; code: string; sticky?: boolean; fill?: boolean }) {
  return (
    <table className={`w-full whitespace-nowrap text-[13px] ${fill ? "h-full" : ""}`}>
      <thead>
        <tr className={`th border-b border-line text-left ${sticky ? "sticky top-0 bg-card" : ""}`}>
          <th className="px-1 py-2">#</th>
          <th className="px-1 py-2">LGA</th>
          <th className="px-1 py-2 text-right">PHCs</th>
          <th className="px-1 py-2">Queues</th>
          <th className="px-1 py-2 text-right">Act now</th>
          <th className="px-1 py-2 text-right">Verify</th>
          <th className="px-1 py-2 text-right">Silent</th>
          <th className="px-1 py-2 text-right">Stale LMIS</th>
          <th className="px-1 py-2 text-right">Reporting</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.lga_id} className="border-b border-line last:border-0 hover:bg-muted">
            <td className="px-1 py-2 text-ink-3 tabular-nums">{r.lga_rank}</td>
            <td className="px-1 py-2 font-medium">
              <Link href={`/state/${code}/lga/${r.lga_id}?month=${month}`} title={r.lga} className="block max-w-[120px] truncate hover:underline">{r.lga}</Link>
            </td>
            <td className="px-1 py-2 text-right tabular-nums">{r.facilities}</td>
            <td className="px-1 py-2"><Bar row={r} /></td>
            <td className="px-1 py-2 text-right font-semibold tabular-nums text-act-now">{r.act_now}</td>
            <td className="px-1 py-2 text-right tabular-nums text-verify-then-act">{r.verify_then_act}</td>
            <td className="px-1 py-2 text-right tabular-nums">{r.silent}</td>
            <td className="px-1 py-2 text-right tabular-nums">{r.stale_commodity}</td>
            <td className="px-1 py-2 text-right tabular-nums">{pct(r.reporting_completeness)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const LEGEND = SEGMENTS.map((s) => ({ ...queueStyle(s.tag), tag: s.tag }));

const ROW_PX = 37;     // natural height of one table row (py-2 + 20px line + border)
const MIN_ROWS = 5;

/** LGAs ranked by action and verification need. In the card: as many rows as fit the height of the map card beside it (the card
 *  has no height of its own on large screens, so it matches its neighbour), with spare height shared out by the rows so there is no
 *  blank space. The full ranking opens in a modal. */
export default function LgaTable({ rows, month, code, limit = 10 }: { rows: any[]; month: string; code: string; limit?: number }) {
  const [open, setOpen] = useState(false);
  const [n, setN] = useState(limit);
  const closeRef = useRef<HTMLButtonElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const shown = Math.min(n, rows.length);
  const more = rows.length > shown;

  useLayoutEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const fit = () => {
      if (!window.matchMedia("(min-width: 1024px)").matches) { setN(limit); return; }   // stacked layout: a fixed short list
      const head = el.querySelector("thead")?.getBoundingClientRect().height ?? 34;
      const room = el.clientHeight - 16 - head;                                            // 16 = the body's padding
      setN(Math.max(MIN_ROWS, Math.floor(room / ROW_PX)));
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    window.addEventListener("resize", fit);
    return () => { ro.disconnect(); window.removeEventListener("resize", fit); };
  }, [limit, rows.length]);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", key);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", key); document.body.style.overflow = overflow; };
  }, [open]);

  return (
    <section className="card relative min-h-[420px] lg:min-h-0" aria-label="LGA table">
      <div className="flex flex-col lg:absolute lg:inset-0">
        <div className="flex shrink-0 items-baseline justify-between px-4 pt-4">
          <h2 className="text-[16px] font-semibold text-ink">LGAs ranked by action and verification need</h2>
          <span className="text-[12px] text-ink-3">Top {shown} of {rows.length}</span>
        </div>
        <div ref={bodyRef} className="min-h-0 flex-1 overflow-x-auto overflow-y-hidden p-2">
          <Table rows={rows.slice(0, shown)} month={month} code={code} fill={more} />
        </div>
        {more && (
          <div className="shrink-0 border-t border-line px-4 py-2.5">
            <button onClick={() => setOpen(true)} className="text-[13px] font-medium text-ink underline-offset-2 hover:underline">
              Show all {rows.length} LGAs →
            </button>
          </div>
        )}
      </div>

      {open && (
        <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/50 p-3 sm:p-6" onClick={() => setOpen(false)}>
          <div
            role="dialog" aria-modal="true" aria-label="All LGAs ranked by action and verification need"
            className="flex max-h-[90vh] w-[min(1000px,100%)] flex-col overflow-hidden rounded-lg border border-line bg-card" onClick={(e) => e.stopPropagation()}
          >
            <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div>
                <h2 className="text-[16px] font-semibold text-ink">All {rows.length} LGAs, ranked by action and verification need</h2>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-2">
                  {LEGEND.map((l) => (
                    <span key={l.tag} className="flex items-center gap-1.5">
                      <i className={`inline-block h-2.5 w-4 rounded-sm ${QUEUE_CLASS[l.token].bar}`} />{l.label}
                    </span>
                  ))}
                </div>
              </div>
              <button
                ref={closeRef} onClick={() => setOpen(false)} aria-label="Close" title="Close (Esc)"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded border border-line bg-card text-[16px] text-ink-2 hover:bg-muted"
              >✕</button>
            </header>
            <div className="overflow-auto p-2"><Table rows={rows} month={month} code={code} sticky /></div>
          </div>
        </div>
      )}
    </section>
  );
}
