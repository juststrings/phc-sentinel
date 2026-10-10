import Icon from "@/components/Icon";
import { QUEUE_CLASS, queueStyle } from "@/lib/tokens";
import type { Metadata } from "next";
import { api, int } from "@/lib/api";

export const metadata: Metadata = { title: "Method & data" };

const FAMILY_LABEL: Record<string, string> = {
  completeness: "Completeness", timeliness: "Timeliness", silence: "Silence", outliers: "Outliers",
  consistency_over_time: "Consistency over time", coherence: "Coherence", freshness: "Freshness",
};
const TOC = [
  ["queues", "1. Two judgements, four queues"],
  ["risk", "2. How risk is assessed"],
  ["confidence", "3. How confidence is assessed"],
  ["thresholds", "4. Thresholds and sources"],
  ["sources", "5. Data sources and coverage"],
  ["access", "6. Access in the demo and a pilot"],
  ["limits", "7. Limitations and scope"],
];
const humanise = (s: string) => s.replace(/_/g, " ");
const show = (v: unknown) => (Array.isArray(v) ? v.join(", ") : typeof v === "boolean" ? (v ? "yes" : "no") : String(v));

function H({ id, children }: { id: string; children: React.ReactNode }) {
  return <h2 id={id} className="scroll-mt-4 text-[20px] font-semibold text-ink">{children}</h2>;
}

function QueueCard({ tag, blurb }: { tag: string; blurb: string }) {
  const s = queueStyle(tag);
  return (
    <div className={`rounded-lg border p-4 ${QUEUE_CLASS[s.token].card}`} data-queue-token={s.token}>
      <div className={`flex items-center gap-1.5 text-[14px] font-semibold ${QUEUE_CLASS[s.token].text}`}><Icon name={s.icon} size={15} />{s.label}</div>
      <p className="mt-1 text-[13px] text-ink-2">{blurb}</p>
    </div>
  );
}

export default async function Method() {
  const [labels, cfg, rules, th, st] = await Promise.all([
    api("/meta/data-labels"), api("/meta/settings"), api("/meta/rules"), api("/meta/thresholds"), api("/national/states"),
  ]);
  const s = cfg.settings;
  const families = [...new Set<string>(rules.rules.map((r: any) => r.family))];

  return (
    <div className="mx-auto grid max-w-[1200px] gap-8 lg:grid-cols-[220px_1fr]">
      <nav aria-label="Contents" className="lg:sticky lg:top-6 lg:self-start">
        <div className="th mb-2">Contents</div>
        <ul className="space-y-1">
          {TOC.map(([id, label]) => <li key={id}><a href={`#${id}`} className="block rounded px-2 py-1 text-[13px] text-ink-2 hover:bg-muted">{label}</a></li>)}
        </ul>
      </nav>

      <div className="space-y-10">
        <div>
          <h1 className="text-[28px] font-semibold leading-9 text-ink">Method</h1>
          <p className="mt-1 max-w-2xl text-[14px] text-ink-2">
            How PHC Sentinel decides, and where every operational number comes from. It helps a State PHC Board choose which facilities to
            support or verify next, with an explicit judgement of how far the underlying data can be trusted.
          </p>
        </div>

        <section className="space-y-3">
          <H id="queues">1. Two judgements, four queues</H>
          <p className="max-w-2xl text-[13px] text-ink-2">
            Every facility gets two separate outputs, operational risk and data confidence, so unverified data cannot hide an emergency.
          </p>
          <div className="grid grid-cols-[28px_1fr_1fr] gap-2">
            <div />
            <div className="th text-center">High or moderate confidence</div>
            <div className="th text-center">Low confidence</div>
            <div className="th flex items-center justify-center [writing-mode:vertical-rl] rotate-180">High or critical risk</div>
            <QueueCard tag="ACT NOW" blurb="Confirmed high risk on trustworthy data. Resource action." />
            <QueueCard tag="VERIFY THEN ACT" blurb="High risk, but the data are stale or unverified. Confirm in the field before dispatching." />
            <div className="th flex items-center justify-center [writing-mode:vertical-rl] rotate-180">Normal or watch risk</div>
            <QueueCard tag="MONITOR" blurb="Adequate stock and routine demand, with trustworthy reports." />
            <QueueCard tag="DO NOT ASSUME SAFE" blurb="Risk looks low, but missing or stale reports mean it cannot be trusted. Data verification." />
          </div>
          <p className="rounded border border-line bg-muted px-3 py-2 text-[13px] text-ink-2">
            <strong>Core principle:</strong> silence is never read as safety, and an overdue report cannot receive high confidence.
          </p>
        </section>

        <section className="space-y-3">
          <H id="risk">2. How risk is assessed</H>
          <p className="max-w-2xl text-[13px] text-ink-2">Operational risk is the worst <em>credible</em> area, never an average. An area whose source is stale is shown but cannot drive risk.</p>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="card p-4">
              <h3 className="text-[14px] font-semibold text-ink">Malaria commodities</h3>
              <p className="mt-1 text-[13px] text-ink-2">
                Months of stock = physical stock / average monthly consumption. Below the {s.commodity.min_months}-month minimum is Watch;
                below the {s.commodity.eop_months}-month emergency order point is High; a stockout with stock below the minimum is Critical.
              </p>
            </div>
            <div className="card p-4">
              <h3 className="text-[14px] font-semibold text-ink">Vaccines &amp; cold chain</h3>
              <p className="mt-1 text-[13px] text-ink-2">
                A stockout with a non-functional refrigerator is Critical; either alone is High. Sessions below {Math.round(s.vaccine.sessions_watch_ratio * 100)}% of
                plan, or Penta1 to Penta3 dropout up {s.vaccine.dropout_rise_points} points on its baseline, is Watch.
              </p>
            </div>
            <div className="card p-4">
              <h3 className="text-[14px] font-semibold text-ink">Service demand</h3>
              <p className="mt-1 text-[13px] text-ink-2">
                Robust z-score against a seasonal baseline: Watch at z ≥ {s.service_pressure.watch_z}, High at z ≥ {s.service_pressure.high_z}.
                {s.service_pressure.requires_corroboration && " Demand is a proxy, so on its own it is capped at Watch unless another area confirms."}
              </p>
            </div>
          </div>
        </section>

        <section className="space-y-3">
          <H id="confidence">3. How confidence is assessed</H>
          <p className="max-w-2xl text-[13px] text-ink-2">
            {rules.rules.length} rules adapted from the WHO Data Quality Review framework. A severe failure means Low confidence; major or minor failures
            mean at most Moderate.
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            {families.map((fam) => {
              const rs = rules.rules.filter((r: any) => r.family === fam);
              return (
                <div key={fam} className="card p-4">
                  <div className="mb-2 flex items-baseline justify-between">
                    <h3 className="text-[14px] font-semibold text-ink">{FAMILY_LABEL[fam] ?? humanise(fam)}</h3>
                    <span className="text-[12px] text-ink-3">{rs.length} {rs.length === 1 ? "rule" : "rules"}</span>
                  </div>
                  <ul className="space-y-2">
                    {rs.map((r: any) => (
                      <li key={r.rule_id} className="text-[13px] text-ink-2">
                        {r.label}
                        <span className="block text-[11px] text-ink-3">
                          <code>{r.rule_id}</code>{r.severities.length > 0 && ` · ${r.severities.join(" or ")}`}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </section>

        <section className="space-y-3">
          <H id="thresholds">4. Thresholds and sources</H>
          <p className="max-w-2xl text-[13px] text-ink-2">
            Read directly from <code>config/settings.yaml</code>. The basis column is the tag recorded beside each value:
            POLICY (published policy), WHO-DQR, STAT (statistical convention) or DESIGN (design judgement).
          </p>
          <div className="card overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="th border-b border-line text-left">
                  <th className="px-3 py-2">Parameter</th><th className="px-3 py-2">Value</th><th className="px-3 py-2">Basis</th><th className="px-3 py-2">Note</th>
                </tr>
              </thead>
              <tbody>
                {th.thresholds.map((t: any) => (
                  <tr key={`${t.section}.${t.key}`} className="border-b border-line last:border-0">
                    <td className="px-3 py-2"><span className="text-ink">{humanise(t.key)}</span><span className="block text-[11px] text-ink-3">{t.section}</span></td>
                    <td className="px-3 py-2 font-medium tabular-nums text-ink">{show(t.value)}</td>
                    <td className="px-3 py-2 text-ink-2">{t.basis ?? <span className="text-ink-3">not tagged</span>}</td>
                    <td className="px-3 py-2 text-ink-3">{t.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <H id="sources">5. Data sources and coverage</H>
          <p className="max-w-2xl text-[13px] text-ink-2">
            Monthly reports follow the DHIS2 dataset &ldquo;{th.dhis2_dataset}&rdquo; (deadline {s.reporting.dhis2_deadline_days} days after month end).
            Commodity reports follow the NHLMIS cycle of {s.reporting.nhlmis_cycle_months} months (deadline {s.reporting.nhlmis_deadline_days} days after period end).
            {" "}{labels.banner}
          </p>
          <div className="card overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead><tr className="th border-b border-line text-left"><th className="px-3 py-2">Table</th><th className="px-3 py-2">Class</th><th className="px-3 py-2">Description</th></tr></thead>
              <tbody>
                {labels.tables.map((t: any) => (
                  <tr key={t.table_name} className="border-b border-line last:border-0">
                    <td className="px-3 py-2"><code>{t.table_name}</code></td>
                    <td className="px-3 py-2 capitalize text-ink-2">{t.data_class}</td>
                    <td className="px-3 py-2 text-ink-2">{t.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <p className="max-w-2xl text-[13px] text-ink-2">
            Coverage is {st.states.length} states, two per geopolitical zone. Facility lists are GRID3 Health Facilities v3.0, filtered to public
            primary facilities. Lagos, Anambra, Rivers and Cross River are not in GRID3 v3.0, so same-zone states stand in: Ogun for Lagos, Abia for
            Anambra, and Delta and Bayelsa for Rivers and Cross River.
          </p>
          <div className="card overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="th border-b border-line text-left">
                  <th className="px-3 py-2">Zone</th><th className="px-3 py-2">State</th>
                  <th className="px-3 py-2 text-right">Public PHCs</th><th className="px-3 py-2 text-right">LGAs</th>
                  <th className="px-3 py-2 text-right">Location unverified</th>
                </tr>
              </thead>
              <tbody>
                {st.states.map((r: any) => (
                  <tr key={r.state_code} className="border-b border-line last:border-0">
                    <td className="px-3 py-2 text-ink-3">{r.zone}</td>
                    <td className="px-3 py-2 font-medium">{r.state}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{int(r.facilities)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{r.lgas}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{r.location_unverified}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="max-w-2xl text-[12px] text-ink-3">
            Each point is checked against its own LGA polygon. Outside it but within {s.geography.near_boundary_km} km is <strong>Near boundary</strong> and
            stays on the map; further away is <strong>Location unverified</strong>: the facility stays in every queue but is not drawn on the map.
          </p>
        </section>

        <section className="space-y-3">
          <H id="access">6. Access in the demo and a pilot</H>
          <div className="card space-y-2 p-4 text-[13px] text-ink-2">
            <p>
              The demo has <strong>no login</strong>: every view has its own address (<code>/national</code>, <code>/state/&#123;code&#125;</code>) so
              reviewers can reach any of them in one click.
            </p>
            <p>
              A pilot would add <strong>real authentication with state-scoped access</strong>: a State PHC Board or LGA team sees only its own state and
              LGAs; federal users (FMoH, NPHCDA) see the national roll-up and can open any state. The API would enforce the same scopes, not only the interface.
            </p>
          </div>
        </section>

        <section className="space-y-3">
          <H id="limits">7. Limitations and scope</H>
          <ul className="list-disc space-y-2 pl-5 text-[13px] text-ink-2">
            <li><strong>Simulated data.</strong> Operational history is simulated over {s.simulator.history_months} months in every state to test the triage logic. We do not claim real-world predictive accuracy.</li>
            <li><strong>Thresholds</strong> come from policy, WHO DQR practice or statistical convention, and are configurable. We do not claim they are optimal.</li>
            <li><strong>Scope</strong> is malaria commodities, vaccines and cold chain, and service demand. General essential medicines and daily staffing are not covered.</li>
            <li><strong>Coordinate anomalies.</strong> Facilities with coordinates outside their LGA stay in the queues so none is silently omitted.</li>
            <li><strong>Pilot.</strong> All data enter through the same DHIS2 / NHLMIS export adapter a state would use. To pilot, replace the export files and edit one mapping file.</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
