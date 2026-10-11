"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { homeOf, type Scope } from "@/lib/scopeCore";
import Icon from "./Icon";
import ViewAs from "./ViewAs";

export type StateInfo = { code: string; name: string; zone: string };

/** The state code in the current URL (/state/{code}/...), if any. */
export function useStateCode(): string | null {
  const m = usePathname().match(/^\/state\/([^/]+)/);
  return m ? m[1] : null;
}

/** Navigation follows the "View as" choice: National sees everything; a state board sees its state; an LGA team sees its LGA. */
export default function Sidebar({ scope, states, lgaName, badge = 0 }: { scope: Scope; states: StateInfo[]; lgaName?: string; badge?: number }) {
  const path = usePathname();
  const month = useSearchParams().get("month");
  const q = month ? `?month=${month}` : "";
  const code = useStateCode();

  const top = (href: string, label: string, icon: string, on: boolean, count = 0) => (
    <Link
      key={href} href={`${href}${q}`} aria-current={on ? "page" : undefined}
      className={`flex items-center gap-2 whitespace-nowrap rounded px-3 py-2 text-[13px] font-medium ${on ? "bg-[var(--brand)] text-[var(--canvas)]" : "text-ink-2 hover:bg-muted"}`}
    >
      <Icon name={icon} />
      {label}
      {count > 0 && <span className="ml-auto rounded-full bg-[var(--q-act)] px-1.5 text-[11px] font-semibold leading-4 text-white tabular-nums" aria-label={`${count} need attention`}>{count > 999 ? "999+" : count}</span>}
    </Link>
  );
  // The selected state's pages: a sub-menu of "States", indented under a guide line.
  const sub = (href: string, label: string, on: boolean) => (
    <Link
      key={href} href={`${href}${q}`} aria-current={on ? "page" : undefined}
      className={`flex items-center whitespace-nowrap rounded px-3 py-1.5 text-[13px] ${on ? "bg-muted font-semibold text-ink" : "text-ink-2 hover:bg-muted"}`}
    >
      {label}
    </Link>
  );

  let links: React.ReactNode;
  if (scope.level === "national") {
    const base = code ? `/state/${code}` : null;
    const stateName = code ? states.find((x) => x.code === code)?.name ?? code : null;
    links = (
      <>
        {top("/national", "National", "home", path === "/national")}
        {top("/states", "States", "building", path === "/states")}
        {base && stateName && (
          <div className="ml-5 hidden border-l border-line pl-2 md:block" role="group" aria-label={`${stateName} pages`}>
            <div className="th px-3 pb-1 pt-1">{stateName}</div>
            {sub(base, "Overview", path === base)}
            {sub(`${base}/lga`, "LGA queues", path.startsWith(`${base}/lga`))}
            {sub(`${base}/facilities`, "Facilities", path.startsWith(`${base}/facilit`))}
            {sub(`${base}/actions`, "Action Centre", path.startsWith(`${base}/actions`))}
            {sub(`${base}/messages`, "Messages", path.startsWith(`${base}/messages`))}
          </div>
        )}
        {top("/facilities", "Facilities", "list", path === "/facilities")}
        {top("/national/responses", "State responses", "arrow", path === "/national/responses")}
        {top("/me", "My cases", "list", path === "/me")}
        {top("/about", "Method", "rule", path === "/about")}
        <Link href="/national/briefing" className="hidden items-center gap-2 rounded px-3 py-2 text-[13px] text-ink-3 hover:bg-muted md:flex">
          <Icon name="arrow" /> Briefing mode
        </Link>
      </>
    );
  } else if (scope.level === "state") {
    const base = `/state/${scope.state}`;
    links = (
      <>
        {top(base, "Overview", "home", path === base)}
        {top(`${base}/lga`, "LGA queues", "list", path.startsWith(`${base}/lga`))}
        {top(`${base}/facilities`, "Facilities", "building", path.startsWith(`${base}/facilit`))}
        {top(`${base}/actions`, "Action Centre", "arrow", path.startsWith(`${base}/actions`))}
        {top(`${base}/messages`, "Messages", "mail", path.startsWith(`${base}/messages`), badge)}
        {top("/me", "My cases", "list", path === "/me")}
        {top("/about", "Method", "rule", path === "/about")}
      </>
    );
  } else {
    const base = `/state/${scope.state}`;
    const home = `${base}/lga/${scope.lga}`;
    links = (
      <>
        {top(home, "Clinic queues", "list", path === home)}
        {top(`${base}/facilities`, "Facilities", "building", path.startsWith(`${base}/facilit`))}
        {top(`${home}/actions`, "Action Centre", "arrow", path.startsWith(`${home}/actions`))}
        {top(`${home}/messages`, "Messages", "mail", path.startsWith(`${home}/messages`), badge)}
        {top("/me", "My cases", "list", path === "/me")}
        {top("/about", "Method", "rule", path === "/about")}
      </>
    );
  }

  return (
    <aside className="shell-chrome border-b border-line bg-card md:sticky md:top-[var(--banner-h,32px)] md:h-[calc(100vh-var(--banner-h,32px))] md:w-60 md:shrink-0 md:overflow-y-auto md:border-b-0 md:border-r">
      <Link href={homeOf(scope)} className="block px-4 py-3 md:px-5 md:py-5" aria-label="PHC Sentinel home">
        <div className="text-[16px] font-bold leading-5 text-ink">PHC Sentinel</div>
        <div className="text-[12px] text-ink-3">Early warning for primary health care</div>
      </Link>
      <ViewAs scope={scope} states={states} lgaName={lgaName} />
      <nav className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:px-3" aria-label="Primary">
        {links}
      </nav>
    </aside>
  );
}
