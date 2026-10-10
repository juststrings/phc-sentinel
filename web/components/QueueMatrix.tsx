import Icon from "./Icon";
import { QUEUE_CLASS, queueStyle } from "@/lib/tokens";

interface Cell { tag: string; n: number; prev?: number; blurb: string }

function Card({ c }: { c: Cell }) {
  const s = queueStyle(c.tag);
  const cls = QUEUE_CLASS[s.token];
  const delta = c.prev == null ? null : c.n - c.prev;
  return (
    <div className={`relative flex flex-col justify-between rounded-lg border p-4 ${cls.card}`} data-queue-token={s.token}>
      <div className={`flex items-center gap-1.5 text-[13px] font-semibold ${cls.text}`}>
        <Icon name={s.icon} size={15} />
        {s.label}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className={`text-[44px] font-bold leading-none tracking-tight tabular-nums ${cls.text}`}>{c.n.toLocaleString()}</span>
        {delta != null && (
          <span className="text-[12px] text-ink-3 tabular-nums">{delta > 0 ? "+" : ""}{delta} vs last month</span>
        )}
      </div>
      <p className="mt-2 text-[12px] leading-4 text-ink-2">{c.blurb}</p>
    </div>
  );
}

/** The 2x2 queue matrix: operational risk (rows) x data confidence (columns). Counts come from /state/summary. */
export default function QueueMatrix({ k, prev }: { k: any; prev?: any }) {
  const cells: Cell[] = [
    { tag: "ACT NOW", n: k.act_now, prev: prev?.act_now, blurb: "High or critical risk on evidence we can trust." },
    { tag: "VERIFY THEN ACT", n: k.verify_then_act, prev: prev?.verify_then_act, blurb: "High or critical risk, but the data are unreliable. Confirm first." },
    { tag: "MONITOR", n: k.monitor, prev: prev?.monitor, blurb: "Normal or watch risk on evidence we can trust." },
    { tag: "DO NOT ASSUME SAFE", n: k.verification, prev: prev?.verification, blurb: "Looks low risk, but the data are too weak to say it is safe." },
  ];
  return (
    <section className="card p-4" aria-label="Queue matrix">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-[16px] font-semibold text-ink">Where each facility sits</h2>
        <span className="text-[12px] text-ink-3">{k.facilities.toLocaleString()} public PHCs</span>
      </div>
      <div className="grid grid-cols-[28px_1fr_1fr] grid-rows-[auto_1fr_1fr] gap-2">
        <div />
        <div className="th text-center">Data confidence: high or moderate</div>
        <div className="th text-center">Data confidence: low</div>
        <div className="th flex items-center justify-center [writing-mode:vertical-rl] rotate-180">High or critical risk</div>
        <Card c={cells[0]} />
        <Card c={cells[1]} />
        <div className="th flex items-center justify-center [writing-mode:vertical-rl] rotate-180">Normal or watch risk</div>
        <Card c={cells[2]} />
        <Card c={cells[3]} />
      </div>
    </section>
  );
}
