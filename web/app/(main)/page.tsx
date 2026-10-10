import Link from "next/link";
import StatusChip from "@/components/StatusChip";
import { api, int, monthLabel, pct } from "@/lib/api";

/** Role switcher. Every view is one click away and has its own URL; no login in the demo. */
export default async function Landing() {
  const [meta, nat, st] = await Promise.all([api("/meta/states"), api("/national/summary"), api("/national/states")]);
  const k = nat.kpis;
  const byCode: Record<string, any> = Object.fromEntries(st.states.map((s: any) => [s.state_code, s]));

  return (
    <div className="mx-auto max-w-[1200px] space-y-8">
      <section>
        <div className="th">Operational risk × data confidence · {monthLabel(nat.month, true)} analysis</div>
        <h1 className="mt-1 text-[34px] font-bold leading-[1.15] tracking-tight text-ink">See risk before it becomes a shortage.</h1>
        <p className="mt-2 max-w-3xl text-[15px] leading-6 text-ink-2">
          PHC Sentinel tells health managers which primary health care facilities need action, which need their data verified first, and why.
          Low observed risk with low confidence is never shown as safe.
        </p>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Link href="/national" className="card block p-5 hover:bg-muted" style={{ borderTopWidth: 4, borderTopColor: "var(--brand)" }}>
          <div className="th">Federal view · FMoH / NPHCDA</div>
          <h2 className="mt-1 text-[22px] font-semibold text-ink">National Command Centre</h2>
          <p className="mt-1 text-[13px] leading-5 text-ink-2">
            State-level summaries across {k.states} states in all six geopolitical zones: where to act, where the evidence is too weak to trust, and how each state is trending.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[[int(k.facilities), "PHCs assessed", "var(--ink)"], [int(k.act_now), "act now", "var(--q-act)"], [int(k.verification), "do not assume safe", "var(--q-dnas)"], [pct(k.reporting_completeness), "reporting", "var(--ink)"]].map(([v, l, c]) => (
              <div key={l} className="rounded border border-line bg-canvas px-3 py-2">
                <b className="block text-[20px] tabular-nums" style={{ color: c }}>{v}</b>
                <span className="text-[11px] text-ink-3">{l}</span>
              </div>
            ))}
          </div>
          <ul className="mt-4 list-disc space-y-1 pl-5 text-[13px] text-ink-2">
            <li>Interactive Nigeria map, coloured by the metric you choose</li>
            <li>A one-click brief for every state, with its top LGAs and six-month trend</li>
            <li>The six geopolitical zones side by side</li>
            <li>Briefing mode: large type, ready to present</li>
          </ul>
          <span className="mt-4 inline-block text-[13px] font-semibold text-ink">Open the Command Centre →</span>
        </Link>

        <section className="card p-5">
          <div className="th">State view · State PHC Board / Agency</div>
          <h2 className="mt-1 text-[22px] font-semibold text-ink">State portal</h2>
          <p className="mt-1 text-[13px] leading-5 text-ink-2">Choose a state to open its overview, LGA action and verification queues, facility directory and explanations.</p>
          <div className="mt-4 grid gap-x-4 gap-y-3 sm:grid-cols-2">
            {meta.zones.map((z: string) => (
              <div key={z}>
                <h3 className="th mb-1">{z}</h3>
                {meta.states.filter((s: any) => s.zone === z).map((s: any) => {
                  const r = byCode[s.code];
                  return (
                    <Link key={s.code} href={`/state/${s.code}`} title={r ? `${r.facilities} PHCs · ${r.act_now} act now` : undefined}
                      className="flex items-center justify-between rounded border border-line bg-card px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-muted [&+&]:mt-1">
                      <span>{s.name}{r && <small className="block text-[11px] font-normal text-ink-3">{int(r.facilities)} PHCs</small>}</span>
                      <span aria-hidden className="text-ink-3">→</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </div>
        </section>
      </div>

      <div role="note" className="rounded border border-line bg-muted px-4 py-3 text-[13px] leading-5 text-ink-2">
        <strong className="text-ink">Demo access, no login.</strong> Every view has its own address (<code>/national</code>, <code>/state/bauchi</code>, …) so reviewers can open any view in one click.
        A pilot deployment adds real authentication with state-scoped access: a state team sees only its own state; federal users see the national roll-up.
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-[18px] font-semibold text-ink">States at a glance</h2>
            <p className="text-[13px] text-ink-3">Status mirrors the Risk × Confidence matrix at state level and is always shown in words.</p>
          </div>
          <Link className="rounded border border-line bg-card px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-muted" href="/national/briefing">Open briefing mode</Link>
        </div>
        <div className="card overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="th border-b border-line text-left">
                <th className="px-3 py-2">State</th><th className="px-3 py-2">Zone</th><th className="px-3 py-2">Status</th>
                <th className="px-3 py-2 text-right">PHCs</th><th className="px-3 py-2 text-right">Act now</th><th className="px-3 py-2 text-right">Do not assume safe</th><th className="px-3 py-2 text-right">Reporting</th>
              </tr>
            </thead>
            <tbody>
              {st.states.map((s: any) => (
                <tr key={s.state_code} className="border-b border-line last:border-0 hover:bg-muted">
                  <td className="px-3 py-2.5"><Link href={`/state/${s.state_code}`} className="font-medium hover:underline">{s.state}</Link></td>
                  <td className="px-3 py-2.5 text-ink-3">{s.zone}</td>
                  <td className="px-3 py-2.5"><StatusChip status={s.status} /></td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{int(s.facilities)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{int(s.act_now)} <span className="text-ink-3">({pct(s.pct_act_now)})</span></td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{int(s.verification)} <span className="text-ink-3">({pct(s.pct_verification)})</span></td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{pct(s.reporting_completeness)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
