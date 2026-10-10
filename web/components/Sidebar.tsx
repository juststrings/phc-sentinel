"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import Icon from "./Icon";

const NAV = [
  { href: "/", label: "State Overview", icon: "home", match: (p: string) => p === "/" },
  { href: "/lga", label: "LGA Queues", icon: "list", match: (p: string) => p.startsWith("/lga") },
  { href: "/facilities", label: "Facilities", icon: "building", match: (p: string) => p.startsWith("/facilit") },
  { href: "/about", label: "Method", icon: "rule", match: (p: string) => p.startsWith("/about") },
];

export default function Sidebar({ state }: { state: string }) {
  const path = usePathname();
  const month = useSearchParams().get("month");
  const q = month ? `?month=${month}` : "";
  return (
    <aside className="border-b border-line bg-card md:sticky md:top-0 md:h-screen md:w-60 md:shrink-0 md:border-b-0 md:border-r">
      <div className="px-4 py-3 md:px-5 md:py-5">
        <div className="text-[16px] font-bold leading-5 text-ink">PHC Sentinel</div>
        <div className="text-[12px] text-ink-3">{state} PHC early warning</div>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:px-3" aria-label="Primary">
        {NAV.map((n) => {
          const active = n.match(path);
          return (
            <Link
              key={n.href}
              href={`${n.href}${q}`}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-2 whitespace-nowrap rounded px-3 py-2 text-[13px] font-medium ${
                active ? "bg-[var(--brand)] text-[var(--canvas)]" : "text-ink-2 hover:bg-muted"
              }`}
            >
              <Icon name={n.icon} />
              {n.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
