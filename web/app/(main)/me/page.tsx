import type { Metadata } from "next";
import ActingAs from "@/components/actions/ActingAs";
import CaseList from "@/components/actions/CaseList";
import ClockBar from "@/components/actions/ClockBar";
import { Kpi } from "@/components/actions/ui";
import { actingOptions, actingPerson } from "@/lib/acting";
import { api } from "@/lib/api";
import { getScope } from "@/lib/scope";

export const metadata: Metadata = { title: "My cases" };

/** Cases owned by, or escalated to, the person you are acting as. */
export default async function MyCases() {
  const scope = await getScope();
  const [acting, options] = await Promise.all([actingPerson(), actingOptions(scope)]);
  const d = await api<any>(`/me/cases?persona_id=${encodeURIComponent(acting.person_id)}&limit=200`);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold leading-8 text-ink">My cases</h1>
          <p className="text-[13px] text-ink-3">{acting.name}, {acting.role_title}. Cases you own or that were escalated to you.</p>
        </div>
        <div className="flex flex-wrap items-end gap-4"><ClockBar clock={d.clock} canReset={scope.level === "national"} /><ActingAs current={acting} options={options} /></div>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <Kpi label="Mine" value={d.cases.length} sub="owned or escalated to me" />
        <Kpi label="Open in my scope" value={d.open_in_scope.toLocaleString()} />
        <Kpi label="Message drafts in my scope" value={d.drafts_in_scope.toLocaleString()} tone="verify" />
      </div>
      <section className="card"><CaseList cases={d.cases} today={d.clock.sim_date} showLga /></section>
    </div>
  );
}
