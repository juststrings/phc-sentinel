import Chip from "./Chip";
import { CommodityChart, ServiceChart } from "./Charts";
import { monthLabel } from "@/lib/api";
import { CONF_STYLE, RISK_STYLE, type Confidence, type Risk } from "@/lib/tokens";

const card = "card p-4";

export function Judgement({ label, children, bg, fg, sub }: { label: string; children: React.ReactNode; bg: string; fg: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-line p-4" style={{ background: bg, color: fg }}>
      <div className="text-[11px] font-semibold uppercase tracking-wider opacity-80">{label}</div>
      <div className="mt-1 text-[28px] font-bold leading-8">{children}</div>
      {sub && <div className="mt-1 text-[13px] opacity-90">{sub}</div>}
    </div>
  );
}

const domainOf = (ex: any, d: string) => ex.domains.find((x: any) => x.domain === d);

function CardHead({ title, dom }: { title: string; dom: any }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <h3 className="text-[14px] font-semibold text-ink">{title}</h3>
      {dom && <Chip kind="risk" value={dom.severity} />}
    </div>
  );
}

function NotCredible({ dom }: { dom: any }) {
  if (!dom || dom.credible) return null;
  return <p className="mb-2 rounded border border-verify-then-act-bd bg-verify-then-act-bg px-2 py-1 text-[12px] text-verify-then-act">Not credible: the source is stale or missing. Shown as context only.</p>;
}

/** Malaria commodities: months-of-stock bars with the policy minimum and emergency order point. */
export function MalariaCard({ ex, trends, cfg }: { ex: any; trends: any[]; cfg: any }) {
  const dom = domainOf(ex, "malaria_commodity");
  const { min_months: min, eop_months: eop, max_months } = cfg.settings.commodity;
  const scale = Math.max(max_months, 1);
  const items = (dom?.evidence ?? []).filter((e: any) => e.mos != null);
  const stale = items.some((e: any) => e.stale);
  const src = items.find((e: any) => e.source_date)?.source_date;
  return (
    <section className={card} aria-label="Malaria commodities">
      <CardHead title="Malaria commodities" dom={dom} />
      <NotCredible dom={dom} />
      {items.length === 0 ? (
        <p className="text-[13px] text-ink-3">No NHLMIS report on record.</p>
      ) : (
        <div className="space-y-3">
          {items.map((e: any) => {
            const w = Math.min(100, (e.mos / scale) * 100);
            const color = e.mos < eop ? "var(--q-act)" : e.mos < min ? "var(--q-verify)" : "var(--q-monitor)";
            return (
              <div key={e.commodity}>
                <div className="mb-1 flex justify-between text-[13px]">
                  <span className="text-ink-2">{e.text.split(":")[0]}</span>
                  <span className="font-semibold tabular-nums text-ink">{e.mos.toFixed(1)} months</span>
                </div>
                <div className="relative h-3 rounded-sm bg-muted">
                  <div className="h-3 rounded-sm" style={{ width: `${w}%`, background: color }} />
                  <span className="absolute inset-y-[-2px] w-px bg-[var(--q-act)]" style={{ left: `${(eop / scale) * 100}%` }} title={`${eop}-month emergency order point`} />
                  <span className="absolute inset-y-[-2px] w-px bg-ink-3" style={{ left: `${(min / scale) * 100}%` }} title={`${min}-month minimum`} />
                </div>
              </div>
            );
          })}
          <div className="text-[11px] text-ink-3">Scale 0 to {scale} months. Red line: {eop}-month emergency order point. Grey line: {min}-month minimum.</div>
        </div>
      )}
      {src && (
        <p className="mt-3 text-[12px] text-ink-3">
          Source: NHLMIS report to {src}
          {stale && <span className="ml-2 rounded-full border border-verify-then-act-bd bg-verify-then-act-bg px-1.5 py-0.5 text-[11px] font-medium text-verify-then-act">stale</span>}
        </p>
      )}
      <details className="mt-3">
        <summary className="cursor-pointer text-[12px] text-ink-3">Months of stock by NHLMIS period</summary>
        <CommodityChart rows={trends} minMonths={min} eopMonths={eop} />
      </details>
    </section>
  );
}

/** Vaccines and cold chain. The engine exposes this domain as evidence text only, so that is what we show. */
export function VaccineCard({ ex }: { ex: any }) {
  const dom = domainOf(ex, "vaccine_cold_chain");
  return (
    <section className={card} aria-label="Vaccines and cold chain">
      <CardHead title="Vaccines & cold chain" dom={dom} />
      <NotCredible dom={dom} />
      {dom?.evidence?.length ? (
        <ul className="list-disc space-y-1.5 pl-4 text-[13px] text-ink-2">
          {dom.evidence.map((e: any, i: number) => <li key={i}>{e.text}</li>)}
        </ul>
      ) : (
        <p className="text-[13px] text-ink-3">No vaccine or cold chain issue found in the latest report.</p>
      )}
    </section>
  );
}

/** Service demand against its seasonal baseline. */
export function DemandCard({ ex, services, capped, month }: { ex: any; services: any[]; capped: boolean; month: string }) {
  const dom = domainOf(ex, "service_pressure");
  return (
    <section className={card} aria-label="Service demand">
      <CardHead title="Service demand" dom={dom} />
      <NotCredible dom={dom} />
      <ServiceChart rows={services} indicator="confirmed_malaria" title="Confirmed malaria vs seasonal baseline, last 18 months" month={month} />
      {dom?.evidence?.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-4 text-[13px] text-ink-2">
          {/* Evidence text already names its indicator. The charted one (confirmed malaria) comes first. */}
          {[...dom.evidence].sort((a: any, b: any) => Number(b.indicator === "confirmed_malaria") - Number(a.indicator === "confirmed_malaria"))
            .map((e: any, i: number) => <li key={i}>{e.text}</li>)}
        </ul>
      )}
      {capped && <p className="mt-2 text-[12px] italic text-ink-3">Demand alone is capped at Watch.</p>}
    </section>
  );
}

const RULE_SEV: Record<string, string> = { severe: "Severe", major: "Major", minor: "Minor" };

export function ConfidenceReasons({ conf, reasons, checks }: { conf: string; reasons: string[]; checks: any[] }) {
  const title = conf === "HIGH" ? "Data confidence is high" : `Why confidence is ${conf.toLowerCase()}`;
  return (
    <section className={`${card} h-full`} aria-label="Why confidence">
      <h3 className="mb-3 text-[14px] font-semibold text-ink">{title}</h3>
      {checks.length === 0 && reasons.length === 0 ? (
        <p className="text-[13px] text-ink-3">All expected reports are current, complete and coherent.</p>
      ) : (
        <ol className="space-y-2">
          {(checks.length ? checks : reasons.map((r) => ({ explanation: r }))).map((c: any, i: number) => (
            <li key={i} className="flex gap-3 text-[13px]">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-semibold text-ink-2">{i + 1}</span>
              <span className="text-ink-2">
                {c.explanation}
                {c.rule_id && <span className="block text-[11px] text-ink-3">{RULE_SEV[c.severity] ?? c.severity} · {c.rule_id}</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/** Last 12 months: risk strip, confidence strip, report arrival markers. Months with no analysis row are skipped. */
export function Strips({ rows }: { rows: any[] }) {
  const last = rows.slice(-12);
  const strip = (pick: (r: any) => { c: string; t: string }) => (
    <div className="flex gap-1">
      {last.map((r) => {
        const { c, t } = pick(r);
        return <div key={r.analysis_month} title={`${monthLabel(r.analysis_month)}: ${t}`} className="h-6 flex-1 rounded-sm" style={{ background: c }} />;
      })}
    </div>
  );
  const arrival = (r: any) => (!r.report_received ? "missing" : r.late_days > 0 ? `${Math.round(r.late_days)} days late` : "on time");
  return (
    <section className={card} aria-label="Last 12 months">
      <h3 className="mb-3 text-[14px] font-semibold text-ink">Last 12 months</h3>
      <div className="space-y-3">
        <div>
          <div className="th mb-1">Operational risk</div>
          {strip((r) => ({ c: RISK_STYLE[r.operational_risk as Risk]?.hex ?? "var(--line)", t: r.operational_risk }))}
        </div>
        <div>
          <div className="th mb-1">Data confidence</div>
          {strip((r) => ({ c: CONF_STYLE[r.data_confidence as Confidence]?.hex ?? "var(--line)", t: r.data_confidence }))}
        </div>
        <div>
          <div className="th mb-1">Monthly report arrival</div>
          <div className="flex gap-1">
            {last.map((r) => {
              const miss = !r.report_received;
              const late = !miss && r.late_days > 0;
              return (
                <div key={r.analysis_month} title={`${monthLabel(r.analysis_month)}: ${arrival(r)}`} className="flex flex-1 justify-center">
                  <span
                    className="h-3.5 w-3.5 rounded-full"
                    style={{
                      background: miss ? "transparent" : late ? "var(--q-verify)" : "var(--q-monitor)",
                      border: miss ? "2px solid var(--ink-3)" : "none",
                    }}
                  />
                </div>
              );
            })}
          </div>
        </div>
        <div className="flex justify-between text-[11px] text-ink-3">
          <span>{last[0] && monthLabel(last[0].analysis_month)}</span>
          <span>{last.length && monthLabel(last[last.length - 1].analysis_month)}</span>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-2">
          <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-[var(--q-monitor)]" />on time</span>
          <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-[var(--q-verify)]" />late</span>
          <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-full border-2 border-ink-3" />missing at analysis date</span>
          <span className="ml-auto">Risk and confidence: darker is worse</span>
        </div>
      </div>
    </section>
  );
}
