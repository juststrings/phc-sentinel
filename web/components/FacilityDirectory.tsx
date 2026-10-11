import Link from "next/link";
import { notFound } from "next/navigation";
import Chip from "@/components/Chip";
import Icon from "@/components/Icon";
import StateSelect from "@/components/StateSelect";
import { DOMAIN_LABEL, api, apiOrNull, int, monthLabel } from "@/lib/api";
import { getScope } from "@/lib/scope";
import { QUEUE_BY_TAG } from "@/lib/tokens";

export type SP = Record<string, string | undefined>;
const PAGE_SIZE = 25;
const sel = "rounded border border-line bg-card px-2 py-1.5 text-[13px] text-ink";

const COLS: { key: string; label: string; global?: boolean }[] = [
  { key: "name", label: "Facility" },
  { key: "state", label: "State", global: true },
  { key: "lga", label: "LGA" },
  { key: "queue", label: "Queue" },
  { key: "risk", label: "Risk" },
  { key: "confidence", label: "Confidence" },
  { key: "last_dhis2", label: "Last DHIS2" },
  { key: "last_nhlmis", label: "NHLMIS report age" },
];

/** PHC directory. With `code` it is that state's directory (/state/{code}/facilities); without it, every state (/facilities)
 *  with a State filter. Filters and sort live in the URL (a plain GET form), so a view can be shared and needs no client JS. */
export default async function FacilityDirectory({ code, sp }: { code?: string; sp: SP }) {
  const base = code ? `/state/${code}/facilities` : "/facilities";
  const meta = await api("/meta/months");
  const month = sp.month ?? meta.latest;
  const page = Math.max(1, Number(sp.page) || 1);
  const sort = sp.sort === "state" && code ? "name" : sp.sort ?? "name";
  const dir = sp.dir === "desc" ? "desc" : "asc";
  const scope = await getScope();
  const lgaView = scope.level === "lga";          // an LGA team gets only its own rows: no state-wide summary or counts
  const states = (await api("/meta/states")).states as { code: string; name: string; zone: string }[];
  const eff = code ?? (states.some((s) => s.code === sp.state) ? sp.state : undefined);   // the state in scope, if any

  const qs = new URLSearchParams({ sort, dir, page: String(page), page_size: String(PAGE_SIZE) });
  if (eff) qs.set("state", eff);
  for (const k of ["q", "lga_id", "tag", "area", "risk", "confidence"]) if (sp[k]) qs.set(k, sp[k]!);
  if (sp.stale) qs.set("stale", "true");
  if (sp.coords) qs.set("unverified", "true");

  const summary = eff && !lgaView ? await apiOrNull(`/state/${eff}/summary`, month) : null;
  if (code && !summary && !lgaView) notFound();
  const [res, coords, cfg] = await Promise.all([
    api(`/facilities?${qs}`, month),
    eff && !lgaView ? api(`/state/${eff}/coords`) : Promise.resolve(null),
    api("/meta/settings"),
  ]);
  const pages = Math.max(1, Math.ceil(res.total / PAGE_SIZE));
  const common = { ...sp, month };
  const href = (over: SP) => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...common, ...over })) if (v) p.set(k, v);
    return `${base}?${p.toString()}`;
  };
  const cols = COLS.filter((c) => !c.global || !code);
  const stateName = (c: string) => states.find((s) => s.code === c)?.name ?? c;
  const unverifiedAll = coords || lgaView || scope.level !== "national" ? null : (await api("/national/states", month)).states.reduce((a: number, s: any) => a + s.location_unverified, 0);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[24px] font-semibold leading-8 text-ink">{summary ? `${summary.state.name} facilities` : lgaView && eff ? `${stateName(eff)}: facilities in your LGA` : "Facilities"}</h1>
        <p className="text-[13px] text-ink-3">
          {summary
            ? `${int(summary.kpis.facilities)} public PHCs across ${summary.lgas.length} LGAs`
            : lgaView ? `${int(res.total)} public PHCs` : `Every public PHC in the ${states.length} covered states`} · {monthLabel(month)}
        </p>
      </div>

      <form method="get" className="card flex flex-wrap items-end gap-3 p-3">
        <input type="hidden" name="month" value={month} />
        {code && scope.level === "national" && <StateSelect states={states} value={code} view="facilities" />}
        <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-[12px] text-ink-3">
          Search
          <input name="q" defaultValue={sp.q ?? ""} placeholder="Facility, ward or ID" className={`${sel} w-full`} />
        </label>
        {!code && (
          <label className="flex flex-col gap-1 text-[12px] text-ink-3">State
            <select name="state" defaultValue={eff ?? ""} className={sel}>
              <option value="">All states</option>
              {states.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
            </select>
          </label>
        )}
        {summary && (
          <label className="flex flex-col gap-1 text-[12px] text-ink-3">LGA
            <select name="lga_id" defaultValue={sp.lga_id ?? ""} className={sel}>
              <option value="">All LGAs</option>
              {[...summary.lgas].sort((a: any, b: any) => a.lga.localeCompare(b.lga)).map((l: any) => <option key={l.lga_id} value={l.lga_id}>{l.lga}</option>)}
            </select>
          </label>
        )}
        <label className="flex flex-col gap-1 text-[12px] text-ink-3">Queue
          <select name="tag" defaultValue={sp.tag ?? ""} className={sel}>
            <option value="">All queues</option>
            {Object.entries(QUEUE_BY_TAG).map(([t, s]) => <option key={t} value={t}>{s.label}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-ink-3">Area
          <select name="area" defaultValue={sp.area ?? ""} className={sel}>
            <option value="">All areas</option>
            {Object.entries(DOMAIN_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-ink-3">Risk
          <select name="risk" defaultValue={sp.risk ?? ""} className={sel}>
            <option value="">All</option>
            {["CRITICAL", "HIGH", "WATCH", "NORMAL"].map((r) => <option key={r} value={r}>{r.charAt(0) + r.slice(1).toLowerCase()}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-ink-3">Confidence
          <select name="confidence" defaultValue={sp.confidence ?? ""} className={sel}>
            <option value="">All</option>
            {["HIGH", "MODERATE", "LOW"].map((r) => <option key={r} value={r}>{r.charAt(0) + r.slice(1).toLowerCase()}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 pb-1.5 text-[13px] text-ink-2">
          <input type="checkbox" name="stale" value="1" defaultChecked={!!sp.stale} /> Stale reports only
        </label>
        <label className="flex items-center gap-2 pb-1.5 text-[13px] text-ink-2">
          <input type="checkbox" name="coords" value="1" defaultChecked={!!sp.coords} /> Location unverified
        </label>
        <button className="rounded bg-[var(--brand)] px-4 py-1.5 text-[13px] font-medium text-[var(--canvas)]">Apply</button>
        <Link href={`${base}?month=${month}`} className="pb-1.5 text-[13px] text-ink-3 hover:underline">Reset</Link>
      </form>

      {!lgaView && (
      <p className="flex items-center gap-2 text-[12px] text-ink-3">
          <Icon name="flag" size={13} />
          {coords && summary
            ? `${coords.unverified} PHCs have coordinates more than ${cfg.settings.geography.near_boundary_km} km outside their own LGA (${coords.outside_state} of them outside ${summary.state.name} State). `
            : `${int(unverifiedAll)} PHCs across all states have coordinates more than ${cfg.settings.geography.near_boundary_km} km outside their own LGA. `}
          They are flagged here and still appear in the queues.
        </p>
      )}

      <section className="card">
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="th border-b border-line text-left">
                {cols.map((c) => {
                  const on = sort === c.key;
                  return (
                    <th key={c.key} className="px-3 py-2" aria-sort={on ? (dir === "asc" ? "ascending" : "descending") : "none"}>
                      <Link href={href({ sort: c.key, dir: on && dir === "asc" ? "desc" : "asc", page: undefined })} className="hover:text-ink">
                        {c.label}{on ? (dir === "asc" ? " ▲" : " ▼") : ""}
                      </Link>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {res.facilities.map((f: any) => (
                <tr key={f.facility_id} className="border-b border-line last:border-0 hover:bg-muted">
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-1.5">
                      <Link href={`/state/${f.state_code}/facility/${f.facility_id}?month=${month}`} className="font-medium hover:underline">{f.name}</Link>
                      {f.coord_status === "location_unverified" && (
                        <span title="Location unverified: coordinates are far outside this facility's LGA" aria-label="Location unverified" className="text-verify-then-act">
                          <Icon name="flag" size={13} />
                        </span>
                      )}
                    </div>
                    <div className="text-[12px] text-ink-3">{f.ward} · <span className="font-mono">{f.facility_id}</span></div>
                  </td>
                  {!code && <td className="px-3 py-2.5 text-ink-2"><Link href={`/state/${f.state_code}?month=${month}`} className="hover:underline">{stateName(f.state_code)}</Link></td>}
                  <td className="px-3 py-2.5 text-ink-2">{f.lga}</td>
                  <td className="px-3 py-2.5"><Chip kind="queue" tag={f.tag} /></td>
                  <td className="px-3 py-2.5"><Chip kind="risk" value={f.operational_risk} /></td>
                  <td className="px-3 py-2.5"><Chip kind="confidence" value={f.data_confidence} /></td>
                  <td className="whitespace-nowrap px-3 py-2.5 tabular-nums text-ink-2">
                    {f.last_dhis2 ? monthLabel(f.last_dhis2) : <span className="italic text-ink-3">none</span>}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 tabular-nums text-ink-2">
                    {f.nhlmis_age_days == null ? <span className="italic text-ink-3">none</span> : `${Math.round(f.nhlmis_age_days)} days`}
                    {f.nhlmis_stale && (
                      <span className="ml-2 rounded-full border border-verify-then-act-bd bg-verify-then-act-bg px-1.5 py-0.5 text-[11px] font-medium text-verify-then-act">stale</span>
                    )}
                  </td>
                </tr>
              ))}
              {res.facilities.length === 0 && (
                <tr><td colSpan={cols.length} className="px-3 py-10 text-center text-ink-3">No facilities match these filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between px-4 py-3 text-[12px] text-ink-3">
          <span>
            Showing {res.total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, res.total)} of {int(res.total)}
          </span>
          <span className="flex items-center gap-2">
            {page > 1 ? <Link className="rounded border border-line px-2 py-1 hover:bg-muted" href={href({ page: String(page - 1) })}>Previous</Link> : <span className="rounded border border-line px-2 py-1 opacity-40">Previous</span>}
            <span className="tabular-nums">Page {page} of {pages}</span>
            {page < pages ? <Link className="rounded border border-line px-2 py-1 hover:bg-muted" href={href({ page: String(page + 1) })}>Next</Link> : <span className="rounded border border-line px-2 py-1 opacity-40">Next</span>}
          </span>
        </div>
      </section>
    </div>
  );
}
