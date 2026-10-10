import Link from "next/link";

export default function NotFound() {
  return (
    <main className="px-4 py-12">
      <div className="card mx-auto max-w-lg p-8 text-center">
        <div className="th">Not found</div>
        <h1 className="mt-1 text-[22px] font-semibold text-ink">That view is not in the demo</h1>
        <p className="mt-2 text-[13px] text-ink-2">The state, LGA or facility may not be covered. Twelve states are available, two per geopolitical zone.</p>
        <div className="mt-4 flex justify-center gap-3 text-[13px] font-medium">
          <Link className="rounded bg-[var(--brand)] px-3 py-1.5 text-[var(--canvas)]" href="/national">National Command Centre</Link>
          <Link className="rounded border border-line bg-card px-3 py-1.5 text-ink hover:bg-muted" href="/">Choose a state</Link>
        </div>
      </div>
    </main>
  );
}
