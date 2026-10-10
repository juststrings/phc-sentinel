import Link from "next/link";
import LgaMap from "@/components/LgaMap";
import { ConfBadge, QueueTag } from "@/components/Tags";
import { DOMAIN_LABEL, api, monthLabel, pct } from "@/lib/api";

const TABS = [
  ["action", "Resource action"],
  ["verification", "Data verification"],
  ["monitor", "Monitor"],
] as const;

function age(r: any) {
  const parts = [];
  if (!r.report_received) parts.push(`${r.consecutive_missing} monthly report${r.consecutive_missing > 1 ? "s" : ""} missing`);
  else if (r.late_days > 0) parts.push(`monthly report ${r.late_days}d late`);
  else parts.push("monthly report on time");
  if (r.nhlmis_age_days == null) parts.push("no NHLMIS report");
  else parts.push(`NHLMIS ${Math.round(r.nhlmis_age_days)}d old`);
  return parts.join(" · ");
}

export default async function LgaQueues({ params, searchParams }: {
  params: Promise<{ id: string }>; searchParams: Promise<{ month?: string; tab?: string }>;
}) {
  const { id } = await params;
  const { month: m, tab = "action" } = await searchParams;
  const meta = await api("/meta/months");
  const month = m ?? meta.latest;
  const [d, lgaGeo, facGeo] = await Promise.all([
    api(`/lga/${id}/queue`, month), api("/geo/lgas", month), api(`/geo/facilities?lga_id=${id}`, month),
  ]);
  const l = d.lga;
  const rows: any[] = d[tab] ?? d.action;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumbs"><Link href={`/?month=${month}`}>Bauchi State</Link> / {l.lga} LGA · {monthLabel(month)}</div>
          <h1>{l.lga} LGA queues</h1>
          <div className="secondary">
            {l.facilities} PHCs · reporting {pct(l.reporting_completeness)} complete, {pct(l.on_time_rate)} on time ·
            ranked #{l.lga_rank} of 20 LGAs
          </div>
        </div>
      </div>

      <div className="grid g-kpi" style={{ marginBottom: 16 }}>
        <div className="card kpi"><div className="label">Act now</div><div className="value num">{l.act_now}</div></div>
        <div className="card kpi"><div className="label">Verify then act</div><div className="value num">{l.verify_then_act}</div></div>
        <div className="card kpi"><div className="label">Data verification</div><div className="value num">{l.verification}</div>
          <div className="sub">{l.reliable_silent} reliable reporters gone silent</div></div>
        <div className="card kpi"><div className="label">Monitor</div><div className="value num">{l.monitor}</div></div>
      </div>

      <div className="grid g-2">
        <div className="card">
          <div className="tabs">
            {TABS.map(([k, label]) => (
              <Link key={k} className={tab === k ? "active" : ""} href={`/lga/${id}?month=${month}&tab=${k}`}>
                {label} ({(d[k] ?? []).length})
              </Link>
            ))}
          </div>
          {tab === "verification" && (
            <p className="muted" style={{ marginTop: 0, fontSize: 12.5 }}>
              These PHCs show no credible warning, but their evidence is too weak to call them safe.
              Ranked with reliable reporters that went silent first, since a break in a strong pattern says the most.
            </p>
          )}
          {rows.length === 0 ? <div className="empty">No facilities in this queue.</div> : (
            <div style={{ overflowX: "auto" }}>
              <table className="data">
                <thead>
                  <tr><th>#</th><th>Facility</th><th>Status</th><th>Evidence and next action</th></tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.facility_id}>
                      <td className="muted num">{r.rank_lga}</td>
                      <td style={{ minWidth: 180 }}>
                        <Link href={`/facility/${r.facility_id}?month=${month}`}>{r.name}</Link>
                        <div className="muted" style={{ fontSize: 12 }}>{r.ward}</div>
                      </td>
                      <td style={{ minWidth: 150 }}>
                        <QueueTag tag={r.tag} />
                        <div style={{ marginTop: 4 }}><ConfBadge conf={r.data_confidence} /></div>
                        {r.queue === "RESOURCE_ACTION" && r.top_domain && (
                          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{DOMAIN_LABEL[r.top_domain]}</div>
                        )}
                      </td>
                      <td style={{ minWidth: 260 }}>
                        {r.evidence_summary}
                        <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{age(r)}</div>
                        <div style={{ marginTop: 6, fontWeight: 600 }}>→ {r.next_action}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="card" style={{ alignSelf: "start" }}>
          <h2>Facilities</h2>
          <LgaMap lgas={lgaGeo} facilities={facGeo} month={month} focusLga={id} />
        </div>
      </div>
    </>
  );
}
