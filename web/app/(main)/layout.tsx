import { Suspense } from "react";
import FacilitySearch from "@/components/FacilitySearch";
import MonthPicker from "@/components/MonthPicker";
import ScopeLabel from "@/components/ScopeLabel";
import Sidebar from "@/components/Sidebar";
import ThemeToggle from "@/components/ThemeToggle";
import { api } from "@/lib/api";

/** App shell for every page except briefing mode: scope-aware sidebar, top bar with month, search and theme toggle. */
export default async function MainLayout({ children }: { children: React.ReactNode }) {
  const [meta, st] = await Promise.all([api("/meta/months"), api("/meta/states")]);
  return (
    <div className="md:flex">
      <Suspense fallback={null}><Sidebar states={st.states} zones={st.zones} /></Suspense>
      <div className="min-w-0 flex-1">
        <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-card px-4 py-3 md:px-6">
          <ScopeLabel states={st.states} />
          <div className="ml-auto flex flex-wrap items-center gap-3">
            <Suspense fallback={null}><MonthPicker months={meta.months} latest={meta.latest} /></Suspense>
            <Suspense fallback={null}><FacilitySearch states={st.states} /></Suspense>
            <ThemeToggle />
          </div>
        </header>
        <main className="p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
