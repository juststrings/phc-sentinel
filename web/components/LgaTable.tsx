import Link from "next/link";
import { pct } from "@/lib/api";
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
    <div className="flex h-2.5 w-full min-w-[80px] overflow-hidden rounded-sm bg-muted" title={title} role="img" aria-label={title}>
      {SEGMENTS.map((s) => {
        const w = (row[s.key] / total) * 100;
        return w > 0 ? <div key={s.key} className={QUEUE_CLASS[queueStyle(s.tag).token].bar} style={{ width: `${w}%` }} /> : null;
      })}
    </div>
  );
}

export default function LgaTable({ rows, month, code }: { rows: any[]; month: string; code: string }) {
  return (
    <section className="card" aria-label="LGA table">
      <div className="flex items-baseline justify-between px-4 pt-4">
        <h2 className="text-[16px] font-semibold text-ink">LGAs ranked by action and verification need</h2>
      </div>
      <div className="overflow-x-auto p-2">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="th border-b border-line text-left">
              <th className="px-1.5 py-2">#</th>
              <th className="px-1.5 py-2">LGA</th>
              <th className="px-1.5 py-2 text-right">PHCs</th>
              <th className="px-1.5 py-2">Queues</th>
              <th className="px-1.5 py-2 text-right">Act now</th>
              <th className="px-1.5 py-2 text-right">Verify</th>
              <th className="px-1.5 py-2 text-right">Silent</th>
              <th className="px-1.5 py-2 text-right">Stale LMIS</th>
              <th className="px-1.5 py-2 text-right">Reporting</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.lga_id} className="border-b border-line last:border-0 hover:bg-muted">
                <td className="px-1.5 py-2 text-ink-3 tabular-nums">{r.lga_rank}</td>
                <td className="px-1.5 py-2 font-medium">
                  <Link href={`/state/${code}/lga/${r.lga_id}?month=${month}`} className="hover:underline">{r.lga}</Link>
                </td>
                <td className="px-1.5 py-2 text-right tabular-nums">{r.facilities}</td>
                <td className="px-1.5 py-2"><Bar row={r} /></td>
                <td className="px-1.5 py-2 text-right font-semibold tabular-nums text-act-now">{r.act_now}</td>
                <td className="px-1.5 py-2 text-right tabular-nums text-verify-then-act">{r.verify_then_act}</td>
                <td className="px-1.5 py-2 text-right tabular-nums">{r.silent}</td>
                <td className="px-1.5 py-2 text-right tabular-nums">{r.stale_commodity}</td>
                <td className="px-1.5 py-2 text-right tabular-nums">{pct(r.reporting_completeness)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
