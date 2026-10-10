"use client";
import { useEffect, useRef, useState } from "react";

export type ModalView = "overview" | "lga" | "facilities";
export const VIEW_LABEL: Record<ModalView, string> = { overview: "Overview", lga: "LGA queues", facilities: "Facilities" };
export const viewPath = (code: string, view: ModalView, month: string) =>
  `/state/${code}${view === "overview" ? "" : view === "lga" ? "/lga" : "/facilities"}?month=${month}`;

/** A state page shown in a modal over the States view. It is the real page in an iframe named "phc-modal"; the root layout hides
 *  the banner and the shell when it runs inside that frame, so only the page content shows. Filters, tabs and links keep working. */
export default function StateModal({ code, name, view, month, onView, onClose }: {
  code: string; name: string; view: ModalView; month: string; onView: (v: ModalView) => void; onClose: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const closeRef = useRef<HTMLButtonElement>(null);
  const src = viewPath(code, view, month);

  useEffect(() => { setLoading(true); }, [src]);
  useEffect(() => {
    closeRef.current?.focus();
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", key);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", key); document.body.style.overflow = overflow; };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/50 p-3 sm:p-6" onClick={onClose}>
      <div
        role="dialog" aria-modal="true" aria-label={`${name}: ${VIEW_LABEL[view]}`}
        className="flex h-[92vh] w-[min(1280px,100%)] flex-col overflow-hidden rounded-lg border border-line bg-canvas"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex flex-wrap items-center gap-3 border-b border-line bg-card px-4 py-2.5">
          <div className="text-[15px] font-semibold text-ink">{name}</div>
          <div className="flex gap-1" role="tablist" aria-label="State views">
            {(Object.keys(VIEW_LABEL) as ModalView[]).map((v) => (
              <button
                key={v} role="tab" aria-selected={v === view} onClick={() => onView(v)}
                className={`rounded border px-2.5 py-1 text-[12px] font-medium ${v === view ? "border-[var(--brand)] bg-[var(--brand)] text-[var(--canvas)]" : "border-line bg-card text-ink-2 hover:bg-muted"}`}
              >{VIEW_LABEL[v]}</button>
            ))}
          </div>
          <a href={src} className="ml-auto text-[12px] font-medium text-ink-2 underline-offset-2 hover:underline" title="Open as a full page">Open full page ↗</a>
          <button
            ref={closeRef} onClick={onClose} aria-label="Close" title="Close (Esc)"
            className="flex h-8 w-8 items-center justify-center rounded border border-line bg-card text-[16px] text-ink-2 hover:bg-muted"
          >✕</button>
        </header>
        <div className="relative flex-1">
          {loading && <div className="absolute inset-0 flex items-center justify-center text-[13px] text-ink-3">Loading {VIEW_LABEL[view].toLowerCase()}…</div>}
          <iframe key={src} name="phc-modal" src={src} title={`${name} ${VIEW_LABEL[view]}`} onLoad={() => setLoading(false)} className="h-full w-full border-0 bg-canvas" />
        </div>
      </div>
    </div>
  );
}
