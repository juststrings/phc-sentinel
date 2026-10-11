import type { Metadata } from "next";
import Link from "next/link";
import ActingAs from "@/components/actions/ActingAs";
import ClockBar from "@/components/actions/ClockBar";
import RequestResponse from "@/components/actions/RequestResponse";
import { CaseStatusPill, Kpi } from "@/components/actions/ui";
import StatusChip from "@/components/StatusChip";
import { actingOptions, actingPerson } from "@/lib/acting";
import { api } from "@/lib/api";
import { getScope } from "@/lib/scope";

export const metadata: Metadata = { title: "State responses" };

/** National works through the state board: ask a state for a response plan, then read its lead and plan. */
export default async function StateResponses() {
  const scope = await getScope();
  const [d, sum, acting, options] = await Promise.all([api<any>("/national/responses"), api<any>("/national/actions/summary"), actingPerson(), actingOptions(scope)]);
  const asked = new Set(d.responses.map((r: any) => r.state_code));
  const k = sum.kpis;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[12px] text-ink-3"><Link href="/national" className="hover:underline">National</Link> / State responses</p>
          <h1 className="text-[24px] font-semibold leading-8 text-ink">State responses</h1>
          <p className="max-w-2xl text-[13px] text-ink-3">When a state&apos;s evidence gap or action load stays high, national can request a response. The state board owns it: it names a lead and submits a plan. Simulated.</p>
        </div>
        <div className="flex flex-wrap items-end gap-4"><ClockBar clock={d.clock} canReset /><ActingAs current={acting} options={options} /></div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Open cases, all states" value={(k.open_cases ?? 0).toLocaleString()} />
        <Kpi label="Overdue" value={(k.overdue ?? 0).toLocaleString()} tone={k.overdue ? "act" : undefined} />
        <Kpi label="Escalated to national" value={(k.escalated_to_national ?? 0).toLocaleString()} tone={k.escalated_to_national ? "verify" : undefined} />
        <Kpi label="State responses" value={d.responses.length} tone="dnas" />
      </div>

      {d.suggested.length > 0 && (
        <section className="card p-4">
          <h2 className="text-[16px] font-semibold text-ink">Suggested</h2>
          <p className="mb-2 text-[12px] text-ink-3">States whose status suggests a response. National decides; nothing is opened automatically.</p>
          <ul className="space-y-2">
            {d.suggested.filter((s: any) => !asked.has(s.state_code)).map((s: any) => (
              <li key={s.state_code} className="flex flex-wrap items-center gap-3 text-[13px]">
                <b className="text-ink">{s.state_name}</b><span className="text-ink-3">{s.zone}</span><StatusChip status={s.status} />
                <span className="text-ink-2">{s.reason}</span><span className="ml-auto"><RequestResponse code={s.state_code} name={s.state_name} /></span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <h2 className="px-4 pt-4 text-[16px] font-semibold text-ink">Requests and responses</h2>
        {d.responses.length === 0 ? <p className="px-4 py-8 text-center text-ink-3">No state has been asked for a response yet.</p> : (
          <div className="overflow-x-auto p-2">
            <table className="w-full text-[13px]">
              <thead><tr className="th border-b border-line text-left"><th className="px-2 py-2">State</th><th className="px-2 py-2">Case</th><th className="px-2 py-2">Status</th><th className="px-2 py-2">Lead</th><th className="px-2 py-2">Plan</th></tr></thead>
              <tbody>
                {d.responses.map((r: any) => (
                  <tr key={r.case_id} className="border-b border-line align-top last:border-0 hover:bg-muted">
                    <td className="px-2 py-2 font-medium text-ink">{r.state_name ?? r.state_code}</td>
                    <td className="px-2 py-2"><Link href={`/cases/${r.case_id}`} className="hover:underline">{r.case_ref}</Link></td>
                    <td className="px-2 py-2"><CaseStatusPill status={r.status} /></td>
                    <td className="px-2 py-2 text-ink-2">{r.response_lead ?? "Not named yet"}</td>
                    <td className="max-w-[420px] px-2 py-2 text-ink-2">{r.response_plan ?? "No plan yet"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
