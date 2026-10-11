import { Suspense } from "react";
import FacilitySearch from "@/components/FacilitySearch";
import MonthPicker from "@/components/MonthPicker";
import ScopeLabel from "@/components/ScopeLabel";
import Sidebar from "@/components/Sidebar";
import ThemeToggle from "@/components/ThemeToggle";
import { api } from "@/lib/api";
import { getScope } from "@/lib/scope";

/** App shell for every page except briefing mode: sidebar with the View-as switcher, top bar with month, search and theme toggle. */
export default async function MainLayout({ children }: { children: React.ReactNode }) {
  const scope = await getScope();
  const [meta, st] = await Promise.all([api("/meta/months"), api("/meta/states")]);
  const lgaName = scope.level === "lga"
    ? (await api(`/meta/lgas?state=${scope.state}`)).lgas.find((l: any) => l.lga_id === scope.lga)?.lga
    : undefined;
  return (
    <div className="md:flex">
      <Suspense fallback={null}><Sidebar scope={scope} states={st.states} lgaName={lgaName} /></Suspense>
      <div className="min-w-0 flex-1">
        <header className="shell-chrome flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-card px-4 py-3 md:px-6">
          <ScopeLabel scope={scope} states={st.states} lgaName={lgaName} />
          <div className="ml-auto flex flex-wrap items-center gap-3">
            <Suspense fallback={null}><MonthPicker months={meta.months} latest={meta.latest} /></Suspense>
            <Suspense fallback={null}><FacilitySearch states={st.states} where={scope.level === "national" ? "all states" : scope.level === "state" ? "your state" : "your LGA"} /></Suspense>
            <ThemeToggle />
          </div>
        </header>
        <main className="p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
