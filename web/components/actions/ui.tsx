import Link from "next/link";

const tone = {
  act: "border-act-now-bd bg-act-now-bg text-act-now",
  verify: "border-verify-then-act-bd bg-verify-then-act-bg text-verify-then-act",
  ok: "border-monitor-bd bg-monitor-bg text-monitor",
  dnas: "border-do-not-assume-safe-bd bg-do-not-assume-safe-bg text-do-not-assume-safe",
  plain: "border-line bg-muted text-ink-2",
};
export type Tone = keyof typeof tone;
const base = "inline-flex items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold leading-4";

export function Pill({ t = "plain", children }: { t?: Tone; children: React.ReactNode }) {
  return <span className={`${base} ${tone[t]}`}>{children}</span>;
}

export const PRIORITY_TONE: Record<string, Tone> = { P1: "act", P2: "verify", P3: "plain" };
export function PriorityPill({ p }: { p: string }) { return <Pill t={PRIORITY_TONE[p] ?? "plain"}>{p}</Pill>; }

export const pretty = (s: string | null | undefined) => (s ?? "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export function CaseStatusPill({ status, overdue }: { status: string; overdue?: boolean }) {
  if (overdue) return <Pill t="act">Overdue</Pill>;
  const t: Tone = status === "resolved" ? "ok" : status.startsWith("closed") ? "plain" : status === "open" ? "verify" : "dnas";
  return <Pill t={t}>{pretty(status)}</Pill>;
}

export function Kpi({ label, value, sub, tone: tn }: { label: string; value: React.ReactNode; sub?: string; tone?: Tone }) {
  const accent = tn === "act" ? "var(--q-act)" : tn === "verify" ? "var(--q-verify)" : tn === "ok" ? "var(--q-monitor)" : tn === "dnas" ? "var(--q-dnas)" : "var(--ink-3)";
  return (
    <div className="card px-3 py-2.5" style={{ borderLeftWidth: 4, borderLeftColor: accent }}>
      <div className="th">{label}</div>
      <div className="text-[22px] font-bold leading-7 tabular-nums text-ink">{value}</div>
      {sub && <div className="text-[11px] text-ink-3">{sub}</div>}
    </div>
  );
}

export function TabLink({ href, on, children }: { href: string; on: boolean; children: React.ReactNode }) {
  return (
    <Link href={href} scroll={false} role="tab" aria-selected={on}
      className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] font-medium ${on ? "border-[var(--brand)] text-ink" : "border-transparent text-ink-2 hover:text-ink"}`}>
      {children}
    </Link>
  );
}

export const SimNote = () => <span className="text-[11px] text-ink-3">Simulated: nothing is ever sent</span>;
