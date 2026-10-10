import Link from "next/link";
import { QueueTrend } from "@/components/Charts";
import LgaMap from "@/components/LgaMap";
import { QueueTag } from "@/components/Tags";
import { DOMAIN_LABEL, api, monthLabel, pct } from "@/lib/api";

export default async function StateOverview({ searchParams }: { searchParams: Promise<{ month?: string }> }) {
  const { month: m } = await searchParams;
  const meta = await api("/meta/months");
  const month = m ?? meta.latest;
  const [s, top, lgaGeo, facGeo] = await Promise.all([
    api("/state/summary", month), api("/state/top", month), api("/geo/lgas", month), api("/geo/facilities", month),
  ]);
  const k = s.kpis;
  const cell = (risk: string, conf: string) => s.matrix.find((x: any) => x.risk === risk && x.confidence === conf)?.n ?? 0;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumbs">Bauchi State · {monthLabel(month)} analysis (as of 30 days after month end)</div>
          <h1>Where to act, where to verify</h1>
          <div className="secondary">{k.facilities.toLocaleString()} public PHCs across {s.lgas.length} LGAs</div>
        </div>
      </div>

      <div className="grid g-kpi" style={{ marginBottom: 16 }}>
        <div className="card kpi">
          <div className="label">Resource action</div>
          <div className="value num">{k.action}</div>
          <div className="sub">{k.act_now} act now · {k.verify_then_act} verify then act</div>
        </div>
        <div className="card kpi">
          <div className="label">Data verification</div>
          <div className="value num">{k.verification}</div>
          <div className="sub">low risk on evidence too weak to trust</div>
        </div>
        <div className="card kpi">
          <div className="label">Monthly reporting completeness</div>
          <div className="value num">{pct(k.reporting_completeness)}</div>
          <div className="sub">{pct(k.on_time_rate)} on time · {k.silent} silent PHCs</div>
        </div>
        <div className="card kpi">
          <div className="label">Stale commodity reports</div>
          <div className="value num">{k.stale_commodity_reports}</div>
          <div className="sub">NHLMIS report overdue or absent</div>
        </div>
      </div>

      <div className="grid g-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <h2>LGAs ranked by action and verification need</h2>
          <div style={{ overflowX: "auto" }}>
            <table className="data">
              <thead>
                <tr>
                  <th>#</th><th>LGA</th><th className="n">PHCs</th><th className="n">Act now</th><th className="n">Verify then act</th>
                  <th className="n">Verification</th><th className="n">Silent</th><th className="n">Stale LMIS</th><th className="n">Reporting</th>
                </tr>
              </thead>
              <tbody>
                {s.lgas.map((l: any) => (
                  <tr key={l.lga_id}>
                    <td className="muted num">{l.lga_rank}</td>
                    <td><Link href={`/lga/${l.lga_id}?month=${month}`}>{l.lga}</Link></td>
                    <td className="n">{l.facilities}</td>
                    <td className="n">{l.act_now}</td>
                    <td className="n">{l.verify_then_act}</td>
                    <td className="n">{l.verification}</td>
                    <td className="n">{l.silent}</td>
                    <td className="n">{l.stale_commodity}</td>
                    <td className="n">{pct(l.reporting_completeness)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="stack">
          <div className="card">
            <h2>Risk × confidence</h2>
            <div className="matrix">
              <div />
              <div className="h">High / moderate confidence</div>
              <div className="h">Low confidence</div>
              <div className="h">High / critical risk</div>
              <div className="cell"><div className="big num">{cell("HIGH_OR_CRITICAL", "HIGH_OR_MODERATE")}</div><QueueTag tag="ACT NOW" /></div>
              <div className="cell"><div className="big num">{cell("HIGH_OR_CRITICAL", "LOW")}</div><QueueTag tag="VERIFY THEN ACT" /></div>
              <div className="h">Normal / watch risk</div>
              <div className="cell"><div className="big num">{cell("NORMAL_OR_WATCH", "HIGH_OR_MODERATE")}</div><QueueTag tag="MONITOR" /></div>
              <div className="cell"><div className="big num">{cell("NORMAL_OR_WATCH", "LOW")}</div><QueueTag tag="DO NOT ASSUME SAFE" /></div>
            </div>
            <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
              Low observed risk with low confidence is not safe: those PHCs go to verification, never to green.
            </p>
          </div>
          <div className="card">
            <h2>What drives resource action</h2>
            <table className="data">
              <tbody>
                {s.action_by_domain.sort((a: any, b: any) => b.n - a.n).map((d: any) => (
                  <tr key={d.top_domain}><td>{DOMAIN_LABEL[d.top_domain] ?? d.top_domain}</td><td className="n">{d.n}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="grid g-half" style={{ marginBottom: 16 }}>
        <div className="card">
          <h2>Map</h2>
          <LgaMap lgas={lgaGeo} facilities={facGeo} month={month} />
        </div>
        <div className="card">
          <h2>Queue sizes over time</h2>
          <QueueTrend data={s.trend} />
          <p className="muted" style={{ fontSize: 12 }}>
            Action rises with the rainy-season malaria peak (Aug to Nov). Verification tracks missing and overdue reports.
          </p>
        </div>
      </div>

      <div className="grid g-half">
        {([["Top of the state action queue", top.action], ["Top of the state verification queue", top.verification]] as const).map(([title, rows]) => (
          <div className="card" key={title}>
            <h2>{title}</h2>
            <table className="data">
              <tbody>
                {rows.map((r: any) => (
                  <tr key={r.facility_id}>
                    <td className="muted num">{r.rank_state}</td>
                    <td>
                      <Link href={`/facility/${r.facility_id}?month=${month}`}>{r.name}</Link>
                      <div className="muted" style={{ fontSize: 12 }}>{r.lga} · {r.evidence_summary}</div>
                    </td>
                    <td><QueueTag tag={r.tag} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </>
  );
}
