import Link from "next/link";
import { pct } from "@/lib/api";

/** "This week": every line is generated from /state/insights. A line is omitted if its data is missing. */
export default function InsightPanel({ ins, month, code }: { ins: any; month: string; code: string }) {
  const items: { key: string; body: React.ReactNode }[] = [];
  const a = ins.most_act_now_lga;
  if (a && a.act_now > 0)
    items.push({
      key: "act",
      body: (
        <>
          <Link className="font-semibold underline-offset-2 hover:underline" href={`/state/${code}/lga/${a.lga_id}?month=${month}`}>{a.lga}</Link>{" "}
          has the most Act now PHCs ({a.act_now}).
        </>
      ),
    });
  const o = ins.lowest_on_time_lga;
  if (o && o.on_time_rate != null)
    items.push({
      key: "ontime",
      body: (
        <>
          <Link className="font-semibold underline-offset-2 hover:underline" href={`/state/${code}/lga/${o.lga_id}?month=${month}`}>{o.lga}</Link>{" "}
          has the lowest on-time reporting: {pct(o.on_time_rate)} of {o.facilities} PHCs.
        </>
      ),
    });
  const p = ins.shortage_by_product?.[0];
  if (p)
    items.push({
      key: "product",
      body: (
        <>
          <span className="font-semibold">{p.product}</span> is the most common shortage: {p.n} PHCs have under{" "}
          {ins.shortage_min_months} months of stock on a current report.
        </>
      ),
    });
  return (
    <section className="card p-4" aria-label="This week">
      <h2 className="mb-3 text-[16px] font-semibold text-ink">This week</h2>
      {items.length === 0 ? (
        <p className="text-ink-3">Nothing stands out this month.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((i) => (
            <li key={i.key} className="rounded border border-line bg-muted px-3 py-2 text-[13px] leading-5 text-ink-2">{i.body}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
