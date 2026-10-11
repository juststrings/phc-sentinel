import { Suspense } from "react";
import FacilitySearch from "@/components/FacilitySearch";
import MonthPicker from "@/components/MonthPicker";
import ScopeLabel from "@/components/ScopeLabel";
import Sidebar from "@/components/Sidebar";
import ThemeToggle from "@/components/ThemeToggle";
import Link from "next/link";
import Icon from "@/components/Icon";
import { api } from "@/lib/api";
import { getScope } from "@/lib/scope";

/** App shell for every page except briefing mode: sidebar with the View-as switcher, top bar with month, search and theme toggle. */
export default async function MainLayout({ children }: { children: React.ReactNode }) {
  const scope = await getScope();
  const [meta, st] = await Promise.all([api("/meta/months"), api("/meta/states")]);
  const lgaName = scope.level === "lga"
    ? (await api(`/meta/lgas?state=${scope.state}`)).lgas.find((l: any) => l.lga_id === scope.lga)?.lga
    : undefined;
  // Messages waiting for you: drafts to approve plus replies to review, for the state board or LGA team in view.
  let badge = 0;
  const mailHref = scope.level === "state" ? `/state/${scope.state}/messages` : scope.level === "lga" ? `/state/${scope.state}/lga/${scope.lga}/messages` : null;
  if (scope.level !== "national") {
    try {
      const s = await api<any>(`/state/${scope.state}/actions/summary${scope.level === "lga" ? `?lga_id=${scope.lga}` : ""}`);
      badge = (s.kpis.awaiting_approval ?? 0) + (s.kpis.replies_to_review ?? 0);
    } catch { /* the action layer is not loaded: no badge */ }
  }
  return (
    <div className="md:flex">
      <Suspense fallback={null}><Sidebar scope={scope} states={st.states} lgaName={lgaName} badge={badge} /></Suspense>
      <div className="min-w-0 flex-1">
        <header className="shell-chrome flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-card px-4 py-3 md:px-6">
          <ScopeLabel scope={scope} states={st.states} lgaName={lgaName} />
          <div className="ml-auto flex flex-wrap items-center gap-3">
            <Suspense fallback={null}><MonthPicker months={meta.months} latest={meta.latest} /></Suspense>
            <Suspense fallback={null}><FacilitySearch states={st.states} where={scope.level === "national" ? "all states" : scope.level === "state" ? "your state" : "your LGA"} /></Suspense>
            {mailHref && (
              <Link href={mailHref} aria-label={`Messages${badge ? `, ${badge} need attention` : ""}`} title="Messages"
                className="relative flex h-8 w-8 items-center justify-center rounded border border-line bg-card text-ink-2 hover:bg-muted">
                <Icon name="mail" size={16} />
                {badge > 0 && <span className="absolute -right-1.5 -top-1.5 rounded-full bg-[var(--q-act)] px-1 text-[10px] font-semibold leading-4 text-white tabular-nums">{badge > 999 ? "999+" : badge}</span>}
              </Link>
            )}
            <ThemeToggle />
          </div>
        </header>
        <main className="p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
