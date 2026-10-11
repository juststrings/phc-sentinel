"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

interface Hit { facility_id: string; name: string; lga: string; ward: string; state_code: string }

export default function FacilitySearch({ states, where = "all states" }: { states: { code: string; name: string }[]; where?: string }) {
  const router = useRouter();
  const month = useSearchParams().get("month");
  const [text, setText] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (text.trim().length < 2) { setHits([]); return; }
    const ctl = new AbortController();
    const t = setTimeout(async () => {
      try {
        const r = await fetch(`/api/search?q=${encodeURIComponent(text.trim())}`, { signal: ctl.signal });
        if (r.ok) setHits(await r.json());
      } catch { /* aborted or offline: keep the previous list */ }
    }, 200);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [text]);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const go = (h: Hit) => {
    setOpen(false); setText("");
    router.push(`/state/${h.state_code}/facility/${h.facility_id}${month ? `?month=${month}` : ""}`);
  };

  return (
    <div ref={box} className="relative w-full max-w-sm">
      <input
        type="search"
        aria-label="Search facilities"
        placeholder={`Search facilities (${where})`}
        value={text}
        onChange={(e) => { setText(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => { if (e.key === "Enter" && hits[0]) go(hits[0]); }}
        className="w-full rounded border border-line bg-card px-3 py-1.5 text-[13px] text-ink placeholder:text-ink-3"
      />
      {open && hits.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded border border-line bg-card">
          {hits.map((h) => (
            <li key={h.facility_id}>
              <button type="button" onClick={() => go(h)} className="block w-full px-3 py-2 text-left hover:bg-muted">
                <div className="text-[13px] font-medium text-ink">{h.name}</div>
                <div className="text-[12px] text-ink-3">{h.ward} · {h.lga} · {states.find((x) => x.code === h.state_code)?.name ?? h.state_code}</div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
