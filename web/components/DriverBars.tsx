import { DOMAIN_LABEL } from "@/lib/api";

/** What drives resource action: facilities in the action queue by their top risk domain. */
export default function DriverBars({ rows }: { rows: { top_domain: string; n: number }[] }) {
  const sorted = [...rows].sort((a, b) => b.n - a.n);
  const total = sorted.reduce((s, r) => s + r.n, 0) || 1;
  const max = Math.max(1, ...sorted.map((r) => r.n));
  return (
    <section className="card p-4" aria-label="What drives resource action">
      <h2 className="mb-3 text-[16px] font-semibold text-ink">What drives resource action</h2>
      <ul className="space-y-3">
        {sorted.map((r) => (
          <li key={r.top_domain}>
            <div className="mb-1 flex justify-between text-[13px]">
              <span className="text-ink-2">{DOMAIN_LABEL[r.top_domain] ?? r.top_domain}</span>
              <span className="tabular-nums text-ink">{r.n} <span className="text-ink-3">({Math.round((r.n / total) * 100)}%)</span></span>
            </div>
            <div className="h-2 rounded-sm bg-muted">
              <div className="h-2 rounded-sm bg-[var(--q-act)]" style={{ width: `${(r.n / max) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
