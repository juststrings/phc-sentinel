import Link from "next/link";
import { actingOptions, actingPerson } from "@/lib/acting";
import { api, monthLabel } from "@/lib/api";
import { getScope } from "@/lib/scope";
import ActingAs from "./ActingAs";
import Approvals from "./Approvals";
import CaseList from "./CaseList";
import ClockBar from "./ClockBar";
import Replies from "./Replies";
import Resupply from "./Resupply";
import { Kpi, Pill, PriorityPill, TabLink, pretty } from "./ui";

type SP = Record<string, string | undefined>;
const PAGE = 50;
const field = "rounded border border-line bg-card px-2 py-1.5 text-[13px] text-ink";

/** The Action Centre for a state, or for one LGA when `lgaId` is given: what was flagged, who owns it, what was sent and what came back.
 *  Every figure and row comes from the API under the chosen view, so an LGA team only ever sees its own LGA. */
export default async function ActionCentreView({ code, lgaId, sp }: { code: string; lgaId?: string; sp: SP }) {
  const scope = await getScope();
  const [acting, options, meta] = await Promise.all([actingPerson(), actingOptions(scope), api<any>("/meta/states")]);
  const stateName = meta.states.find((s: any) => s.code === code)?.name ?? code;
  const lgaQ = lgaId ? `&lga_id=${lgaId}` : "";
  const sum = await api<any>(`/state/${code}/actions/summary?${lgaQ.slice(1)}`);
  const k = sum.kpis, today = sum.clock.sim_date;
  const base = lgaId ? `/state/${code}/lga/${lgaId}/actions` : `/state/${code}/actions`;
  const tab = ["cases", "approvals", "replies", "resupply"].includes(sp.tab ?? "") ? sp.tab! : "cases";
  const showResupply = !lgaId && scope.level !== "lga";
  const lgaName = lgaId ? (await api<any>(`/meta/lgas?state=${code}`)).lgas.find((l: any) => l.lga_id === lgaId)?.lga : undefined;
  const month = sp.month;
  const mq = month ? `&month=${month}` : "";
  const tabHref = (t: string) => `${base}?tab=${t}${mq}`;

  // data for the open tab
  let body: React.ReactNode = null;
  if (tab === "cases") {
    const page = Math.max(1, Number(sp.page) || 1);
    const qs = new URLSearchParams({ limit: String(PAGE), offset: String((page - 1) * PAGE), sort: sp.sort ?? "priority" });
    const status = sp.status ?? "open";
    if (status === "all") qs.set("open_only", "false"); else if (status !== "open") qs.set("status", status);
    for (const f of ["priority", "rule", "q"]) if (sp[f]) qs.set(f, sp[f]!);
    const filterLga = lgaId ?? sp.lga_id;
    if (filterLga) qs.set("lga_id", filterLga);
    if (sp.overdue) qs.set("overdue", "true");
    if (sp.escalated) qs.set("escalated", "true");
    const cs = await api<any>(`/state/${code}/cases?${qs}`);
    const pages = Math.max(1, Math.ceil(cs.total / PAGE));
    const link = (over: SP) => { const p = new URLSearchParams({ tab: "cases" }); for (const [a, b] of Object.entries({ ...sp, ...over })) if (b && a !== "tab") p.set(a, b); return `${base}?${p}`; };
    body = (
      <>
        <form method="get" className="flex flex-wrap items-end gap-3 border-b border-line px-4 py-3">
          <input type="hidden" name="tab" value="cases" />
          {month && <input type="hidden" name="month" value={month} />}
          <label className="flex min-w-[180px] flex-1 flex-col gap-1 text-[11px] text-ink-3">Search<input name="q" defaultValue={sp.q ?? ""} placeholder="Facility, case or LGA" className={field} /></label>
          <label className="flex flex-col gap-1 text-[11px] text-ink-3">Status
            <select name="status" defaultValue={status} className={field}>
              <option value="open">Open</option><option value="all">All</option>
              {["resolved", "closed_no_action", "closed_duplicate"].map((s) => <option key={s} value={s}>{pretty(s)}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-ink-3">Priority
            <select name="priority" defaultValue={sp.priority ?? ""} className={field}><option value="">All</option><option>P1</option><option>P2</option><option>P3</option></select>
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-ink-3">Rule
            <select name="rule" defaultValue={sp.rule ?? ""} className={`${field} max-w-[220px]`}>
              <option value="">All rules</option>
              {Object.entries(sum.rules as Record<string, string>).map(([id, d]) => <option key={id} value={id}>{pretty(id.replace(/^R\d+_/, ""))}</option>)}
            </select>
          </label>
          {!lgaId && scope.level !== "lga" && (
            <label className="flex flex-col gap-1 text-[11px] text-ink-3">LGA
              <select name="lga_id" defaultValue={sp.lga_id ?? ""} className={field}>
                <option value="">All LGAs</option>
                {[...sum.lgas].sort((a: any, b: any) => a.lga.localeCompare(b.lga)).map((l: any) => <option key={l.lga_id} value={l.lga_id}>{l.lga}</option>)}
              </select>
            </label>
          )}
          <label className="flex items-center gap-1.5 pb-1.5 text-[12px] text-ink-2"><input type="checkbox" name="overdue" value="1" defaultChecked={!!sp.overdue} /> Overdue</label>
          <label className="flex items-center gap-1.5 pb-1.5 text-[12px] text-ink-2"><input type="checkbox" name="escalated" value="1" defaultChecked={!!sp.escalated} /> Escalated</label>
          <button className="rounded bg-[var(--brand)] px-3 py-1.5 text-[13px] font-medium text-[var(--canvas)]">Apply</button>
          <Link href={`${base}?tab=cases${mq}`} className="pb-1.5 text-[12px] text-ink-3 hover:underline">Reset</Link>
        </form>
        <CaseList cases={cs.cases} today={today} showLga={!lgaId} />
        <div className="flex items-center justify-between px-4 py-3 text-[12px] text-ink-3">
          <span>{cs.total.toLocaleString()} case{cs.total === 1 ? "" : "s"} · page {page} of {pages}</span>
          <span className="flex gap-2">
            {page > 1 ? <Link className="rounded border border-line px-2 py-1 hover:bg-muted" href={link({ page: String(page - 1) })}>Previous</Link> : <span className="rounded border border-line px-2 py-1 opacity-40">Previous</span>}
            {page < pages ? <Link className="rounded border border-line px-2 py-1 hover:bg-muted" href={link({ page: String(page + 1) })}>Next</Link> : <span className="rounded border border-line px-2 py-1 opacity-40">Next</span>}
          </span>
        </div>
      </>
    );
  } else if (tab === "approvals") {
    const ms = sp.mstatus ?? "draft";
    const m = await api<any>(`/messages?state=${code}${lgaQ}&limit=50${ms === "all" ? "" : `&status=${ms}`}`);
    body = (
      <>
        <div className="flex items-center gap-2 border-b border-line px-4 py-2 text-[12px] text-ink-2">
          {[["draft", "Awaiting approval"], ["sent_simulated,delivered_simulated,replied", "Sent (simulated)"], ["all", "All"]].map(([v, l]) => (
            <Link key={v} href={`${base}?tab=approvals&mstatus=${v}${mq}`} className={`rounded-full border px-2.5 py-1 ${ms === v ? "border-[var(--brand)] bg-[var(--brand)] text-[var(--canvas)]" : "border-line hover:bg-muted"}`}>{l}</Link>
          ))}
        </div>
        <Approvals messages={m.messages} total={m.total} />
      </>
    );
  } else if (tab === "replies") {
    const rs = sp.rstatus ?? "all";
    const r = await api<any>(`/responses?state=${code}${lgaQ}&limit=100${rs === "review" ? "&review_status=needs_review" : ""}`);
    body = (
      <>
        <div className="flex items-center gap-2 border-b border-line px-4 py-2 text-[12px] text-ink-2">
          {[["all", "All replies"], ["review", "Needs review"]].map(([v, l]) => (
            <Link key={v} href={`${base}?tab=replies&rstatus=${v}${mq}`} className={`rounded-full border px-2.5 py-1 ${rs === v ? "border-[var(--brand)] bg-[var(--brand)] text-[var(--canvas)]" : "border-line hover:bg-muted"}`}>{l}</Link>
          ))}
        </div>
        <Replies responses={r.responses} />
      </>
    );
  } else if (tab === "resupply" && showResupply) {
    body = <Resupply requests={(await api<any>(`/state/${code}/resupply-requests`)).requests} code={code} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[12px] text-ink-3">
            {scope.level === "national" && <><Link href={`/national${month ? `?month=${month}` : ""}`} className="hover:underline">National</Link> / </>}
            {scope.level !== "lga" ? <Link href={`/state/${code}`} className="hover:underline">{stateName}</Link> : stateName}
            {lgaId && <> / {lgaName ?? lgaId}</>} / Action Centre
          </p>
          <h1 className="text-[24px] font-semibold leading-8 text-ink">Action Centre{lgaId ? `: ${lgaName ?? lgaId}` : `: ${stateName}`}</h1>
          <p className="text-[13px] text-ink-3">
            Flagged PHCs become cases with an owner, a deadline and an escalation path. Messages are drafted for a person to approve; sending and replies are simulated.
            Assessment: {monthLabel(sum.clock.baseline_month)}.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <ClockBar clock={sum.clock} canReset={scope.level === "national"} />
          <ActingAs current={acting} options={options} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Kpi label="Open cases" value={k.open_cases.toLocaleString()} sub={`${k.total_cases.toLocaleString()} in total`} />
        <Kpi label="P1 open" value={k.p1_open.toLocaleString()} sub="act within 2 days" tone="act" />
        <Kpi label="Overdue" value={k.overdue.toLocaleString()} sub={k.open_cases ? `${Math.round((k.pct_overdue ?? 0) * 100)}% of open` : undefined} tone={k.overdue ? "act" : undefined} />
        <Kpi label="Escalated" value={k.escalated.toLocaleString()} sub={`${k.escalated_to_state} to state · ${k.escalated_to_national} to national`} tone={k.escalated ? "verify" : undefined} />
        <Kpi label="Awaiting approval" value={k.awaiting_approval.toLocaleString()} sub="message drafts" tone="verify" />
        <Kpi label="Replies to review" value={k.replies_to_review.toLocaleString()} sub={`${k.replies} replies in total`} tone={k.replies_to_review ? "dnas" : undefined} />
        <Kpi label="Resolved" value={k.resolved.toLocaleString()} sub={k.pct_resolved_in_sla != null ? `${Math.round(k.pct_resolved_in_sla * 100)}% within SLA` : "none yet"} tone="ok" />
      </div>

      {!lgaId && scope.level !== "lga" && (
        <div className="grid gap-4 lg:grid-cols-3">
          <section className="card lg:col-span-2">
            <div className="flex items-baseline justify-between px-4 pt-4"><h2 className="text-[16px] font-semibold text-ink">LGA accountability</h2><span className="text-[12px] text-ink-3">worst first: overdue, then unacknowledged</span></div>
            <div className="max-h-[360px] overflow-auto p-2">
              <table className="w-full text-[13px]">
                <thead><tr className="th sticky top-0 border-b border-line bg-card text-left"><th className="px-2 py-2">LGA</th><th className="px-2 py-2">Coordinator</th><th className="px-2 py-2 text-right">Open</th><th className="px-2 py-2 text-right">P1</th><th className="px-2 py-2 text-right">Overdue</th><th className="px-2 py-2 text-right">Unacknowledged</th><th className="px-2 py-2 text-right">Escalated</th></tr></thead>
                <tbody>
                  {sum.lgas.map((l: any) => (
                    <tr key={l.lga_id} className="border-b border-line last:border-0 hover:bg-muted">
                      <td className="px-2 py-2 font-medium"><Link className="hover:underline" href={`/state/${code}/lga/${l.lga_id}/actions${month ? `?month=${month}` : ""}`}>{l.lga}</Link></td>
                      <td className="px-2 py-2 text-ink-2">{l.coordinator ?? "None"}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{l.open_cases}</td>
                      <td className="px-2 py-2 text-right tabular-nums text-act-now">{l.p1_open}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{l.overdue}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{l.unacknowledged}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{l.escalated}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="card p-4">
            <h2 className="text-[16px] font-semibold text-ink">Escalations</h2>
            <p className="mb-2 text-[12px] text-ink-3">Cases that were not acknowledged or ran past their deadline move up the ladder: LGA officer, LGA coordinator, state officer, state director, national.</p>
            {sum.escalations.length === 0 ? <p className="py-4 text-[13px] text-ink-3">None yet. Advance the simulated clock to see what happens when cases are not acknowledged.</p> : (
              <ul className="space-y-2">
                {sum.escalations.map((c: any) => (
                  <li key={c.case_id} className="text-[13px]">
                    <Link href={`/cases/${c.case_id}`} className="font-medium hover:underline">{c.unit_name ?? c.case_ref}</Link> <PriorityPill p={c.priority} />
                    <div className="text-[11px] text-ink-3">Level {c.escalation_level}: now with {c.escalated_to_name ?? c.escalated_to_role} · due {c.due_at}</div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      <section className="card">
        <div className="flex gap-1 overflow-x-auto border-b border-line px-2" role="tablist">
          <TabLink href={tabHref("cases")} on={tab === "cases"}>Cases <Pill>{k.open_cases.toLocaleString()}</Pill></TabLink>
          <TabLink href={tabHref("approvals")} on={tab === "approvals"}>Approvals <Pill t={k.awaiting_approval ? "verify" : "plain"}>{k.awaiting_approval.toLocaleString()}</Pill></TabLink>
          <TabLink href={tabHref("replies")} on={tab === "replies"}>Replies <Pill t={k.replies_to_review ? "dnas" : "plain"}>{k.replies.toLocaleString()}</Pill></TabLink>
          {showResupply && <TabLink href={tabHref("resupply")} on={tab === "resupply"}>Resupply <Pill>{k.resupply_pending.toLocaleString()}</Pill></TabLink>}
        </div>
        {body}
      </section>
    </div>
  );
}
