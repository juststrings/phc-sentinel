import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ActingAs from "@/components/actions/ActingAs";
import Approvals from "@/components/actions/Approvals";
import CasePanel from "@/components/actions/CasePanel";
import ClockBar from "@/components/actions/ClockBar";
import Replies from "@/components/actions/Replies";
import { CaseStatusPill, Pill, PriorityPill, pretty } from "@/components/actions/ui";
import Chip from "@/components/Chip";
import { actingOptions, actingPerson } from "@/lib/acting";
import { ApiError, apiOrNull } from "@/lib/api";
import { getScope } from "@/lib/scope";

export const metadata: Metadata = { title: "Case" };

const Card = ({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) => (
  <section className="card">
    <div className="flex items-baseline justify-between px-4 pt-4"><h2 className="text-[16px] font-semibold text-ink">{title}</h2>{right}</div>
    <div className="p-4 pt-3">{children}</div>
  </section>
);

export default async function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const scope = await getScope();
  let d: any;
  try {
    d = await apiOrNull(`/cases/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) {
      return (
        <div className="card mx-auto mt-10 max-w-lg p-8 text-center">
          <h1 className="text-[20px] font-semibold text-ink">That case is outside this view</h1>
          <p className="mt-2 text-[13px] text-ink-2">You are viewing as a narrower scope than this case belongs to. Switch the view to open it.</p>
        </div>
      );
    }
    throw e;
  }
  if (!d) notFound();
  const c = d.case;
  const [acting, options] = await Promise.all([actingPerson(), actingOptions(scope)]);
  const today = d.clock.sim_date;
  const overdue = c.due_at < today && !["resolved", "closed_no_action", "closed_duplicate"].includes(c.status);
  const home = c.facility_id ? `/state/${c.state_code}/facility/${c.facility_id}` : null;
  const msgs = d.messages.map((m: any) => ({ ...m, priority: c.priority, case_id: undefined, case_ref: c.case_ref }));
  const expecting = d.messages.some((m: any) => m.expects && m.to_person_id === acting.person_id);
  const stateLevel = c.level === "state";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[12px] text-ink-3">
            {scope.level !== "lga" ? <Link href={`/state/${c.state_code}/actions`} className="hover:underline">Action Centre</Link> : <Link href={`/state/${c.state_code}/lga/${scope.lga}/actions`} className="hover:underline">Action Centre</Link>}
            {" / "}{c.case_ref}
          </p>
          <h1 className="text-[24px] font-semibold leading-8 text-ink">{c.unit_name ?? c.case_ref}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-[13px] text-ink-2">
            <PriorityPill p={c.priority} /><CaseStatusPill status={c.status} overdue={overdue} />
            {c.tag && <Chip kind="queue" tag={c.tag} />}
            <span>{pretty(d.rule?.id?.replace(/^R\d+_/, "") ?? c.rule_id)}</span>
            {c.lga && <span>· {c.lga} LGA</span>}
            {home && <Link href={home} className="underline-offset-2 hover:underline">Open facility page</Link>}
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <ClockBar clock={d.clock} canReset={scope.level === "national"} />
          <ActingAs current={acting} options={options} />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-8">
          <Card title="Why this case exists">
            <p className="text-[14px] leading-6 text-ink">{c.evidence_summary}</p>
            {d.rule && <p className="mt-2 text-[12px] text-ink-3">Rule {d.rule.id}: {d.rule.description}</p>}
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[13px] sm:grid-cols-4">
              <div><dt className="text-[11px] text-ink-3">Owner</dt><dd className="text-ink">{c.owner_name ?? "Unassigned"}<span className="block text-[11px] text-ink-3">{c.owner_role_title}</span></dd></div>
              <div><dt className="text-[11px] text-ink-3">Opened</dt><dd className="tabular-nums text-ink">{c.opened_at}</dd></div>
              <div><dt className="text-[11px] text-ink-3">Due</dt><dd className={`tabular-nums ${overdue ? "text-act-now" : "text-ink"}`}>{c.due_at}</dd></div>
              <div><dt className="text-[11px] text-ink-3">Acknowledged</dt><dd className="tabular-nums text-ink">{c.acknowledged_at ?? "Not yet"}</dd></div>
            </dl>
          </Card>

          <Card title="Playbook" right={<span className="text-[12px] text-ink-3">{d.playbook.title}</span>}>
            <ol className="space-y-2">
              {d.playbook.steps.map((s: any, i: number) => {
                const state = i < c.current_step ? "done" : i === c.current_step ? "now" : "next";
                return (
                  <li key={s.id} className="flex items-start gap-3 text-[13px]">
                    <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold ${state === "done" ? "border-monitor-bd bg-monitor-bg text-monitor" : state === "now" ? "border-[var(--brand)] bg-[var(--brand)] text-[var(--canvas)]" : "border-line text-ink-3"}`}>{state === "done" ? "✓" : i + 1}</span>
                    <span className={state === "next" ? "text-ink-3" : "text-ink"}>{s.title} <span className="text-[11px] text-ink-3">{s.kind}</span></span>
                  </li>
                );
              })}
            </ol>
          </Card>

          <section className="card">
            <h2 className="px-4 pt-4 text-[16px] font-semibold text-ink">Messages <span className="text-[12px] font-normal text-ink-3">simulated, approved by a person</span></h2>
            <Approvals messages={msgs} total={msgs.length} />
          </section>

          <section className="card">
            <h2 className="px-4 pt-4 text-[16px] font-semibold text-ink">Replies</h2>
            <Replies responses={d.responses} />
          </section>

          {d.resupply.length > 0 && (
            <Card title="Resupply request">
              <ul className="space-y-1 text-[13px]">
                {d.resupply.map((r: any) => <li key={r.request_id}>{r.commodity_code}: {Math.round(r.qty_requested).toLocaleString()} <Pill t={r.status === "approved" ? "ok" : "verify"}>{String(r.status).replace(/_/g, " ")}</Pill></li>)}
              </ul>
              <p className="mt-2 text-[12px] text-ink-3">Approve requests in the state Action Centre. Nothing moves stock.</p>
            </Card>
          )}
        </div>

        <div className="space-y-4 lg:col-span-4">
          <CasePanel
            caseId={c.case_id} status={c.status} owner={c.owner_name}
            people={d.people.filter((p: any) => p.level !== "national" || scope.level === "national")}
            outcomes={d.outcome_codes} actingLevel={acting.level} hasExpectingMessage={expecting}
          />
          <Card title="Escalation ladder">
            <ol className="space-y-2">
              {d.escalation_ladder.map((s: any) => (
                <li key={s.level} className={`rounded border px-2.5 py-1.5 text-[13px] ${s.level === c.escalation_level ? "border-[var(--brand)] bg-muted" : "border-line"}`}>
                  <div className="flex justify-between"><b className="text-ink">{s.title}</b><span className="text-[11px] text-ink-3">{s.sla_days} day{s.sla_days === 1 ? "" : "s"}</span></div>
                  <div className="text-[12px] text-ink-3">{s.name ?? "Vacant"}{s.level === c.escalation_level ? " · holds it now" : ""}</div>
                </li>
              ))}
            </ol>
          </Card>
          {d.live && !stateLevel && (
            <Card title="Live status">
              <p className="text-[13px] text-ink-2">Baseline: <b>{d.live.baseline_tag}</b> · Live: <b>{d.live.live_tag}</b>{d.live.field_verified ? " (field verified)" : ""}</p>
              {d.live.live_reasons && <p className="mt-1 text-[12px] text-ink-3">{Array.isArray(d.live.live_reasons) ? d.live.live_reasons.join(" · ") : String(d.live.live_reasons)}</p>}
            </Card>
          )}
        </div>
      </div>

      <Card title="Timeline">
        <ol className="space-y-2">
          {[...d.events].reverse().map((e: any) => (
            <li key={e.event_id} className="flex gap-3 text-[13px]">
              <span className="w-24 shrink-0 tabular-nums text-ink-3">{String(e.at).slice(0, 10)}</span>
              <span className="text-ink-2"><b className="text-ink">{pretty(e.event_type)}</b>{e.actor ? ` · ${e.actor}` : ""}{e.to_status ? ` · ${pretty(e.to_status)}` : ""}
                {e.payload?.text ? <span className="block text-[12px] text-ink-3">{e.payload.text}</span> : null}</span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
