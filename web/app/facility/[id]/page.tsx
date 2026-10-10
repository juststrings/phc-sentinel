import Link from "next/link";
import { CommodityChart, ServiceChart } from "@/components/Charts";
import { ConfBadge, QueueTag, SevBadge } from "@/components/Tags";
import { QUEUE_LABEL, api, monthLabel } from "@/lib/api";

const SEV_ORDER: Record<string, number> = { severe: 0, major: 1, minor: 2 };

export default async function FacilityExplanation({ params, searchParams }: {
  params: Promise<{ id: string }>; searchParams: Promise<{ month?: string }>;
}) {
  const { id } = await params;
  const { month: m } = await searchParams;
  const meta = await api("/meta/months");
  const month = m ?? meta.latest;
  const [d, qd, cfg] = await Promise.all([api(`/facility/${id}`, month), api(`/quality/${id}`, month), api("/meta/settings")]);
  const f = d.facility, s = d.status, ex = d.explanation;
  const reasons: string[] = ex.confidence_reasons ?? [];
  const checks = [...(qd.checks ?? [])].sort((a: any, b: any) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumbs">
            <Link href={`/?month=${month}`}>Bauchi State</Link> / <Link href={`/lga/${f.lga_id}?month=${month}`}>{f.lga} LGA</Link> / {f.ward}
          </div>
          <h1>{f.name}</h1>
          <div className="secondary">
            {f.facility_type || "Primary health facility"} · {f.ownership_type || "public"} · GRID3 {f.facility_id}
            {f.coord_status === "invalid" && " · coordinates flagged invalid in GRID3"}
          </div>
        </div>
      </div>

      <div className="grid g-half" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="secondary" style={{ fontSize: 12 }}>Operational risk</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "6px 0 10px" }}>
            <SevBadge sev={s.operational_risk} />
            <span className="muted">worst credible domain{s.pressure_capped ? " (service pressure alone capped at Watch)" : ""}</span>
          </div>
          <div className="secondary" style={{ fontSize: 12 }}>Queue</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "6px 0 12px", flexWrap: "wrap" }}>
            <strong>{QUEUE_LABEL[s.queue]}</strong> <QueueTag tag={s.tag} />
            <span className="muted">#{s.rank_lga} in {f.lga} · #{s.rank_state} in state</span>
          </div>
          <div className="action-box">{s.next_action}</div>
        </div>
        <div className="card">
          <div className="secondary" style={{ fontSize: 12 }}>Data confidence</div>
          <div style={{ margin: "6px 0 10px" }}><ConfBadge conf={s.data_confidence} /></div>
          {reasons.length ? (
            <>
              <div className="secondary" style={{ fontSize: 12 }}>Why confidence is reduced</div>
              <ul className="evidence">{reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </>
          ) : <p className="muted">All expected reports current, complete and coherent.</p>}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Why flagged: evidence by domain</h2>
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
          {ex.domains.map((dm: any) => (
            <div key={dm.domain} style={{ borderTop: "1px solid var(--grid)", paddingTop: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                <h3 style={{ margin: 0 }}>{dm.label}</h3>
                <SevBadge sev={dm.severity} muted={!dm.credible} />
              </div>
              {!dm.credible && (
                <div className="sev" style={{ color: "var(--st-serious)", marginTop: 4 }}>
                  NOT CREDIBLE: source stale or missing; shown as context only
                </div>
              )}
              <ul className="evidence" style={{ marginTop: 6 }}>
                {dm.evidence.map((e: any, i: number) => (
                  <li key={i}>
                    {e.text}
                    {e.source_date && <span className="muted"> (report to {e.source_date}{e.age_days != null ? `, ${e.age_days} days old` : ""})</span>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <div className="grid g-half" style={{ marginBottom: 16 }}>
        <div className="card">
          <ServiceChart rows={d.trends.services} indicator="confirmed_malaria" title="Confirmed malaria vs seasonal baseline" />
        </div>
        <div className="card">
          <ServiceChart rows={d.trends.services} indicator="opd" title="OPD attendance vs seasonal baseline" />
        </div>
      </div>

      <div className="grid g-half" style={{ marginBottom: 16 }}>
        <div className="card">
          <h3>Malaria commodity position by NHLMIS period</h3>
          <CommodityChart rows={d.trends.commodity} minMonths={cfg.settings.commodity.min_months} eopMonths={cfg.settings.commodity.eop_months} />
          <table className="data" style={{ marginTop: 8 }}>
            <thead><tr><th>Commodity</th><th>Latest period</th><th className="n">Age (days)</th><th>Status</th></tr></thead>
            <tbody>
              {qd.freshness.map((r: any) => (
                <tr key={r.commodity_code}>
                  <td>{r.commodity_code}</td>
                  <td>{r.has_record ? `${r.period_start} to ${r.nhlmis_period_end}` : "none"}</td>
                  <td className="n">{r.nhlmis_age_days ?? "n/a"}</td>
                  <td>{r.stale_flag ? <span className="sev" style={{ color: "var(--st-critical)" }}>STALE: {r.next_expected_period} overdue</span> : "current"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Reporting history</h3>
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginBottom: 6 }}>
            {d.trends.reporting.map((r: any) => (
              <div key={r.analysis_month} title={`${monthLabel(r.analysis_month)}: ${!r.report_received ? "missing" : r.late_days > 0 ? `${r.late_days} days late` : "on time"}`}
                style={{
                  width: 18, height: 22, borderRadius: 3,
                  background: !r.report_received ? "transparent" : r.late_days > 0 ? "var(--st-warning)" : "var(--seq-400)",
                  border: !r.report_received ? "1.5px solid var(--st-critical)" : "none",
                }} />
            ))}
          </div>
          <div className="legend">
            <span><i style={{ background: "var(--seq-400)" }} />on time</span>
            <span><i style={{ background: "var(--st-warning)" }} />late</span>
            <span><i style={{ border: "1.5px solid var(--st-critical)" }} />missing at analysis date</span>
          </div>
          <h3 style={{ marginTop: 16 }}>Failed data quality checks ({checks.length})</h3>
          {checks.length === 0 ? <p className="muted">None.</p> : (
            <table className="data">
              <tbody>
                {checks.map((c: any, i: number) => (
                  <tr key={i}>
                    <td style={{ width: 70 }}><span className="sev" style={{ color: c.severity === "severe" ? "var(--st-critical)" : "var(--text-secondary)" }}>{c.severity.toUpperCase()}</span></td>
                    <td>{c.explanation}<div className="muted" style={{ fontSize: 11.5 }}>{c.rule_id} · {c.family}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
