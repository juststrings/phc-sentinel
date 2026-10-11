import Link from "next/link";
import { actingOptions, actingPerson } from "@/lib/acting";
import { api } from "@/lib/api";
import { getScope } from "@/lib/scope";
import ActingAs from "./ActingAs";
import Approvals from "./Approvals";
import ClockBar from "./ClockBar";
import Replies from "./Replies";
import { Pill, TabLink } from "./ui";

type SP = Record<string, string | undefined>;

/** Messaging for a state or one LGA: drafts waiting for approval, what was sent, and the replies that came back (inbox).
 *  Everything is simulated: a person approves each draft, and nothing is ever sent. */
export default async function MessagesView({ code, lgaId, sp }: { code: string; lgaId?: string; sp: SP }) {
  const scope = await getScope();
  const [acting, options, meta] = await Promise.all([actingPerson(), actingOptions(scope), api<any>("/meta/states")]);
  const stateName = meta.states.find((s: any) => s.code === code)?.name ?? code;
  const lgaQ = lgaId ? `&lga_id=${lgaId}` : "";
  const sum = await api<any>(`/state/${code}/actions/summary?${lgaQ.slice(1)}`);
  const k = sum.kpis;
  const lgaName = lgaId ? (await api<any>(`/meta/lgas?state=${code}`)).lgas.find((l: any) => l.lga_id === lgaId)?.lga : undefined;
  const base = lgaId ? `/state/${code}/lga/${lgaId}/messages` : `/state/${code}/messages`;
  const tab = ["drafts", "sent", "replies"].includes(sp.tab ?? "") ? sp.tab! : "drafts";
  const mq = sp.month ? `&month=${sp.month}` : "";
  const href = (t: string) => `${base}?tab=${t}${mq}`;

  let body: React.ReactNode;
  if (tab === "replies") {
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
  } else {
    const status = tab === "drafts" ? "draft" : "sent_simulated,delivered_simulated,replied,failed_simulated";
    const m = await api<any>(`/messages?state=${code}${lgaQ}&limit=50&status=${status}`);
    body = <Approvals messages={m.messages} total={m.total} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[12px] text-ink-3">
            {scope.level !== "lga" ? <Link href={`/state/${code}`} className="hover:underline">{stateName}</Link> : stateName}
            {lgaId && <> / {lgaName ?? lgaId}</>} / Messages
          </p>
          <h1 className="text-[24px] font-semibold leading-8 text-ink">Messages{lgaId ? `: ${lgaName ?? lgaId}` : `: ${stateName}`}</h1>
          <p className="max-w-2xl text-[13px] text-ink-3">
            Messages are drafted from templates for the right person at each step of a case. A person approves a draft before it goes out, and replies
            come back here. Sending is simulated.
            {" "}<Link href={lgaId ? `/state/${code}/lga/${lgaId}/actions` : `/state/${code}/actions`} className="underline-offset-2 hover:underline">Open the Action Centre</Link> for the cases behind them.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-4"><ClockBar clock={sum.clock} canReset={scope.level === "national"} /><ActingAs current={acting} options={options} /></div>
      </div>
      <section className="card">
        <div className="flex gap-1 overflow-x-auto border-b border-line px-2" role="tablist">
          <TabLink href={href("drafts")} on={tab === "drafts"}>To approve <Pill t={k.awaiting_approval ? "verify" : "plain"}>{k.awaiting_approval.toLocaleString()}</Pill></TabLink>
          <TabLink href={href("sent")} on={tab === "sent"}>Sent (simulated) <Pill>{k.sent.toLocaleString()}</Pill></TabLink>
          <TabLink href={href("replies")} on={tab === "replies"}>Inbox: replies <Pill t={k.replies_to_review ? "dnas" : "plain"}>{k.replies.toLocaleString()}</Pill></TabLink>
        </div>
        {body}
      </section>
    </div>
  );
}
