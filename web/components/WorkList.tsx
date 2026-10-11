"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import Chip from "./Chip";
import Icon from "./Icon";
import { DOMAIN_LABEL } from "@/lib/format";
import { isOverdue, lastReport, toCsv, whyText } from "@/lib/queues";

const PAGE = 25;
const sel = "rounded border border-line bg-card px-2 py-1.5 text-[13px] text-ink";

/** Ranked work list for one queue. Filters apply to the list; Export CSV downloads exactly the filtered rows. */
export default function WorkList({ rows, month, filename, code }: { rows: any[]; month: string; filename: string; code: string }) {
  const [area, setArea] = useState("");
  const [conf, setConf] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [page, setPage] = useState(1);

  const filtered = useMemo(
    () => rows.filter((r) => (!area || r.top_domain === area) && (!conf || r.data_confidence === conf) && (!overdue || isOverdue(r))),
    [rows, area, conf, overdue],
  );
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const cur = Math.min(page, pages);
  const shown = filtered.slice((cur - 1) * PAGE, cur * PAGE);
  const areas = [...new Set(rows.map((r) => r.top_domain))];

  const exportCsv = () => {
    const url = URL.createObjectURL(new Blob([toCsv(filtered)], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };
  const reset = (fn: () => void) => { fn(); setPage(1); };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
        <label className="flex items-center gap-2 text-[13px] text-ink-2">
          Area
          <select className={sel} value={area} onChange={(e) => reset(() => setArea(e.target.value))}>
            <option value="">All areas</option>
            {areas.map((a) => <option key={a} value={a}>{DOMAIN_LABEL[a] ?? a}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 text-[13px] text-ink-2">
          Confidence
          <select className={sel} value={conf} onChange={(e) => reset(() => setConf(e.target.value))}>
            <option value="">All</option>
            <option value="HIGH">High</option>
            <option value="MODERATE">Moderate</option>
            <option value="LOW">Low</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-[13px] text-ink-2">
          <input type="checkbox" checked={overdue} onChange={(e) => reset(() => setOverdue(e.target.checked))} />
          Overdue only
        </label>
        <button
          type="button" onClick={exportCsv} disabled={filtered.length === 0}
          className="ml-auto flex items-center gap-1.5 rounded border border-line bg-card px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-muted disabled:opacity-50"
        >
          <Icon name="download" /> Export CSV
        </button>
      </div>

      {filtered.length === 0 ? (
        <p className="px-4 py-8 text-center text-ink-3">No facilities match these filters.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="th border-b border-line text-left">
                <th className="px-4 py-2">#</th>
                <th className="px-2 py-2">Facility</th>
                <th className="px-2 py-2">Risk and confidence</th>
                <th className="px-2 py-2">Area</th>
                <th className="px-2 py-2">Why</th>
                <th className="px-2 py-2">Next action</th>
                <th className="px-2 py-2">Last report</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r, i) => (
                <tr key={r.facility_id} className="border-b border-line align-top last:border-0 hover:bg-muted">
                  <td className="px-4 py-3 text-ink-3 tabular-nums">{(cur - 1) * PAGE + i + 1}</td>
                  <td className="px-2 py-3">
                    <Link href={`/state/${code}/facility/${r.facility_id}?month=${month}`} className="font-medium hover:underline">{r.name}</Link>
                    <div className="text-[12px] text-ink-3">{r.ward}</div>
                  </td>
                  <td className="px-2 py-3">
                    <div className="flex flex-wrap gap-1"><Chip kind="risk" value={r.operational_risk} /><Chip kind="confidence" value={r.data_confidence} /></div>
                  </td>
                  <td className="px-2 py-3 text-ink-2">{DOMAIN_LABEL[r.top_domain] ?? r.top_domain}</td>
                  <td className="max-w-[320px] px-2 py-3 text-ink-2">{whyText(r)}</td>
                  <td className="max-w-[260px] px-2 py-3 text-ink">{r.next_action}</td>
                  <td className="whitespace-nowrap px-2 py-3 tabular-nums text-ink-2">
                    {lastReport(r)}
                    {isOverdue(r) && (
                      <span className="ml-2 rounded-full border border-verify-then-act-bd bg-verify-then-act-bg px-1.5 py-0.5 text-[11px] font-medium text-verify-then-act">
                        Overdue{r.overdue_days > 0 ? ` ${Math.round(r.overdue_days)}d` : ""}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between px-4 py-3 text-[12px] text-ink-3">
        <span>
          Showing {filtered.length === 0 ? 0 : (cur - 1) * PAGE + 1}–{Math.min(cur * PAGE, filtered.length)} of {filtered.length}
          {filtered.length !== rows.length && ` (filtered from ${rows.length})`}
        </span>
        <span className="flex items-center gap-2">
          <button type="button" className="rounded border border-line px-2 py-1 disabled:opacity-40" disabled={cur <= 1} onClick={() => setPage(cur - 1)}>Previous</button>
          <span className="tabular-nums">Page {cur} of {pages}</span>
          <button type="button" className="rounded border border-line px-2 py-1 disabled:opacity-40" disabled={cur >= pages} onClick={() => setPage(cur + 1)}>Next</button>
        </span>
      </div>
    </div>
  );
}
