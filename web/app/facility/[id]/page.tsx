import Link from "next/link";
import Chip from "@/components/Chip";
import { ConfidenceReasons, DemandCard, Judgement, MalariaCard, Strips, VaccineCard } from "@/components/FacilityParts";
import Icon from "@/components/Icon";
import { whyText } from "@/lib/queues";
import { ApiError, DOMAIN_LABEL, api, monthLabel } from "@/lib/api";
import { CONF_LABEL, CONF_STYLE, RISK_LABEL, RISK_STYLE, type Confidence, type Risk } from "@/lib/tokens";

const SEV_ORDER: Record<string, number> = { severe: 0, major: 1, minor: 2 };

export default async function FacilityDetail({ params, searchParams }: {
  params: Promise<{ id: string }>; searchParams: Promise<{ month?: string }>;
}) {
  const { id } = await params;
  const { month: m } = await searchParams;
  const meta = await api("/meta/months");
  const month = m ?? meta.latest;

  let d: any, qd: any;
  const cfg = await api("/meta/settings");
  try {
    [d, qd] = await Promise.all([api(`/facility/${id}`, month), api(`/quality/${id}`, month)]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      // Unknown facility, or one with no analysis row for this month: say so plainly.
      return (
        <div className="card mx-auto mt-10 max-w-lg p-8 text-center">
          <h1 className="text-[20px] font-semibold text-ink">{e.message.includes("unknown facility") ? "Facility not found" : "No data for this month"}</h1>
          <p className="mt-2 text-[13px] text-ink-2">
            {e.message.includes("unknown facility") ? "No facility has this ID." : `There is no analysis for this facility in ${monthLabel(month)}. Pick another month, or go back to the directory.`}
          </p>
          <div className="mt-4 flex justify-center gap-3 text-[13px]">
            <Link className="rounded border border-line px-3 py-1.5 hover:bg-muted" href="/facilities">Facilities</Link>
            <Link className="rounded border border-line px-3 py-1.5 hover:bg-muted" href={`/?month=${meta.latest}`}>Latest month</Link>
          </div>
        </div>
      );
    }
    throw e;
  }
  const f = d.facility, s = d.status, ex = d.explanation;
  const risk = RISK_STYLE[s.operational_risk as Risk], conf = CONF_STYLE[s.data_confidence as Confidence];
  const checks = [...(qd.checks ?? [])].sort((a: any, b: any) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]);

  return (
    <div className="mx-auto max-w-[1280px] space-y-4">
      <div>
        <p className="text-[12px] text-ink-3">
          <Link href={`/facilities?month=${month}`} className="hover:underline">Facilities</Link> /{" "}
          <Link href={`/lga/${f.lga_id}?month=${month}`} className="hover:underline">{f.lga}</Link>
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-[24px] font-semibold leading-8 text-ink">{f.name}</h1>
          <Chip kind="queue" tag={s.tag} />
        </div>
        <p className="text-[13px] text-ink-3">
          {f.ward} ward · {f.lga} LGA · <span className="font-mono">{f.facility_id}</span> · {monthLabel(month)}
          {f.coord_status === "invalid" && (
            <span className="ml-2 inline-flex items-center gap-1 text-verify-then-act"><Icon name="flag" size={12} /> coordinates outside this LGA</span>
          )}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-8">
          <div className="grid gap-3 sm:grid-cols-2">
            <Judgement label="Operational risk" bg={risk?.bg} fg={risk?.fg}
              sub={`${DOMAIN_LABEL[s.top_domain] ?? s.top_domain}${s.pressure_capped ? " · service demand alone capped at Watch" : ""}`}>
              {RISK_LABEL[s.operational_risk as Risk] ?? s.operational_risk}
            </Judgement>
            <Judgement label="Data confidence" bg={conf?.bg} fg={conf?.fg}
              sub={ex.confidence_reasons?.[0] ?? "Reports current, complete and coherent"}>
              {CONF_LABEL[s.data_confidence as Confidence] ?? s.data_confidence}
            </Judgement>
          </div>
          <section className="card p-4">
            <div className="th mb-1">Summary</div>
            <p className="text-[15px] leading-6 text-ink">{whyText(s)}</p>
            <p className="mt-2 text-[12px] text-ink-3">Ranked #{s.rank_lga} in {f.lga} and #{s.rank_state} in the state within its queue.</p>
          </section>
        </div>
        <div className="space-y-4 lg:col-span-4">
          <section className="card p-4" style={{ borderLeftWidth: 4, borderLeftColor: "var(--q-verify)" }}>
            <div className="th mb-1">Next action</div>
            <p className="text-[15px] font-medium leading-6 text-ink">{s.next_action}</p>
          </section>
          <section className="card p-4">
            <div className="th mb-2">Facility record</div>
            <dl className="space-y-1 text-[13px]">
              {[["Type", f.facility_type], ["Ownership", f.ownership_type], ["Functional status", f.functional_status], ["NHFR code", f.nhfr_code],
                ["Latitude", f.latitude?.toFixed(4)], ["Longitude", f.longitude?.toFixed(4)]].filter(([, v]) => v).map(([k, v]) => (
                <div key={k as string} className="flex justify-between gap-3"><dt className="text-ink-3">{k}</dt><dd className="text-right text-ink">{v}</dd></div>
              ))}
            </dl>
            <p className="mt-2 text-[11px] text-ink-3">Source: GRID3 facility registry.</p>
          </section>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <MalariaCard ex={ex} trends={d.trends.commodity} cfg={cfg} />
        <VaccineCard ex={ex} />
        <DemandCard ex={ex} services={d.trends.services} capped={!!s.pressure_capped} month={month} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ConfidenceReasons conf={s.data_confidence} reasons={ex.confidence_reasons ?? []} checks={checks} />
        <Strips rows={d.trends.reporting} />
      </div>
    </div>
  );
}
