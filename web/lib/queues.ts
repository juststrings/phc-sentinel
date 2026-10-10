import { DOMAIN_LABEL, monthLabel } from "./api";

/** The four queue tabs. The API groups ACT NOW and VERIFY THEN ACT together as "action"; the tag splits them. */
export const QUEUE_TABS = [
  { key: "act-now", tag: "ACT NOW", source: "action" },
  { key: "verify-then-act", tag: "VERIFY THEN ACT", source: "action" },
  { key: "do-not-assume-safe", tag: "DO NOT ASSUME SAFE", source: "verification" },
  { key: "monitor", tag: "MONITOR", source: "monitor" },
] as const;

/** Rows for one tab, in the engine's ranking order (rank_lga), never alphabetical. */
export function tabRows(d: any, tag: string, source: string): any[] {
  return (d[source] as any[]).filter((r) => r.tag === tag).sort((a, b) => a.rank_lga - b.rank_lga);
}

export function isOverdue(r: any): boolean {
  return !r.report_received || (r.overdue_days ?? 0) > 0;
}

export function lastReport(r: any): string {
  return r.last_report_month ? monthLabel(r.last_report_month) : "never";
}

const csvCell = (v: unknown) => {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function toCsv(rows: any[]): string {
  const head = ["Rank", "Facility", "Ward", "Queue", "Risk", "Confidence", "Area", "Reason", "Next action", "Last report", "Overdue"];
  const lines = rows.map((r) => [
    r.rank_lga, r.name, r.ward, r.tag, r.operational_risk, r.data_confidence, DOMAIN_LABEL[r.top_domain] ?? r.top_domain,
    r.evidence_summary, r.next_action, lastReport(r), isOverdue(r) ? "yes" : "no",
  ]);
  return [head, ...lines].map((l) => l.map(csvCell).join(",")).join("\r\n");
}
