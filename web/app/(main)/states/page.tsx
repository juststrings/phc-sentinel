import type { Metadata } from "next";
import StateCards from "@/components/national/StateCards";
import { api, monthLabel } from "@/lib/api";

export const metadata: Metadata = { title: "States" };

/** State-level view: every covered state as a card, with filters. Cards lead to each state's overview, LGA queues and facilities. */
export default async function States({ searchParams }: {
  searchParams: Promise<{ month?: string; zone?: string; state?: string; status?: string; q?: string; sort?: string; brief?: string }>;
}) {
  const sp = await searchParams;
  const meta = await api("/meta/months");
  const month = sp.month ?? meta.latest;
  const [summary, st, states] = await Promise.all([api("/national/summary", month), api("/national/states", month), api("/meta/states")]);

  return (
    <div className="space-y-4">
      <div>
        <p className="text-[12px] text-ink-3">National / States</p>
        <h1 className="text-[24px] font-semibold leading-8 text-ink">States</h1>
        <p className="text-[13px] text-ink-3">
          {states.states.length} states in all six zones · {monthLabel(month, true)} · status is shown in words and mirrors the risk and confidence matrix at state level
        </p>
      </div>
      <StateCards key={month} states={st.states} zones={summary.zones.map((z: any) => z.zone)} month={month}
        initial={{ zone: sp.zone, state: sp.state, status: sp.status, q: sp.q, sort: sp.sort, brief: sp.brief }} />
    </div>
  );
}
