"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Icon from "./Icon";

export type StateInfo = { code: string; name: string; zone: string };

/** The state code in the current URL (/state/{code}/...), if any. */
export function useStateCode(): string | null {
  const m = usePathname().match(/^\/state\/([^/]+)/);
  return m ? m[1] : null;
}

/** National Command Centre or any of the covered states, grouped by zone. Demo access has no login. */
function ScopeSwitcher({ states, zones }: { states: StateInfo[]; zones: string[] }) {
  const router = useRouter();
  const path = usePathname();
  const month = useSearchParams().get("month");
  const code = useStateCode();
  const value = code ? `/state/${code}` : path.startsWith("/national") ? "/national" : "";
  return (
    <label className="block px-3 pb-3">
      <span className="th mb-1 block">View</span>
      <select
        aria-label="Choose a view"
        value={value}
        onChange={(e) => e.target.value && router.push(`${e.target.value}${month ? `?month=${month}` : ""}`)}
        className="w-full rounded border border-line bg-card px-2 py-1.5 text-[13px] font-medium text-ink"
      >
        {!value && <option value="">Choose a view</option>}
        <option value="/national">National Command Centre</option>
        {zones.map((z) => (
          <optgroup key={z} label={z}>
            {states.filter((s) => s.zone === z).map((s) => <option key={s.code} value={`/state/${s.code}`}>{s.name}</option>)}
          </optgroup>
        ))}
      </select>
    </label>
  );
}

export default function Sidebar({ states, zones }: { states: StateInfo[]; zones: string[] }) {
  const path = usePathname();
  const month = useSearchParams().get("month");
  const code = useStateCode();
  const q = month ? `?month=${month}` : "";
  const base = code ? `/state/${code}` : null;
  const nav = [
    { href: "/national", label: "National", icon: "home", on: path === "/national" },
    { href: "/states", label: "States", icon: "building", on: path === "/states" },
    ...(base ? [
      { href: base, label: "State Overview", icon: "home", on: path === base },
      { href: `${base}/lga`, label: "LGA Queues", icon: "list", on: path.startsWith(`${base}/lga`) },
    ] : []),
    base
      ? { href: `${base}/facilities`, label: "Facilities", icon: "building", on: path.startsWith(`${base}/facilit`) }
      : { href: "/facilities", label: "Facilities", icon: "building", on: path.startsWith("/facilities") },
    { href: "/about", label: "Method", icon: "rule", on: path === "/about" },
  ];
  return (
    <aside className="shell-chrome border-b border-line bg-card md:sticky md:top-[var(--banner-h,32px)] md:h-[calc(100vh-var(--banner-h,32px))] md:w-60 md:shrink-0 md:overflow-y-auto md:border-b-0 md:border-r">
      <Link href="/" className="block px-4 py-3 md:px-5 md:py-5" aria-label="PHC Sentinel home">
        <div className="text-[16px] font-bold leading-5 text-ink">PHC Sentinel</div>
        <div className="text-[12px] text-ink-3">Early warning for primary health care</div>
      </Link>
      <ScopeSwitcher states={states} zones={zones} />
      <nav className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:px-3" aria-label="Primary">
        {nav.map((n) => (
          <Link
            key={n.href}
            href={`${n.href}${q}`}
            aria-current={n.on ? "page" : undefined}
            className={`flex items-center gap-2 whitespace-nowrap rounded px-3 py-2 text-[13px] font-medium ${
              n.on ? "bg-[var(--brand)] text-[var(--canvas)]" : "text-ink-2 hover:bg-muted"
            }`}
          >
            <Icon name={n.icon} />
            {n.label}
          </Link>
        ))}
        <Link href="/national/briefing" className="hidden items-center gap-2 rounded px-3 py-2 text-[13px] text-ink-3 hover:bg-muted md:flex">
          <Icon name="arrow" /> Briefing mode
        </Link>
      </nav>
    </aside>
  );
}
