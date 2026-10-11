"use client";
import { usePathname } from "next/navigation";
import type { Scope } from "@/lib/scopeCore";
import type { StateInfo } from "./Sidebar";
import { useStateCode } from "./Sidebar";
import { scopeTitle } from "./ViewAs";

/** Top-bar label: what you are looking at. A state or LGA view names its own scope; National names the page or state open. */
export default function ScopeLabel({ scope, states, lgaName }: { scope: Scope; states: StateInfo[]; lgaName?: string }) {
  const path = usePathname();
  const code = useStateCode();
  if (scope.level !== "national") {
    const t = scopeTitle(scope, states, lgaName);
    return <div className="text-[14px] font-semibold text-ink">{t.where}<span className="ml-2 text-[12px] font-normal text-ink-3">{t.who}</span></div>;
  }
  const st = code ? states.find((s) => s.code === code) : undefined;
  if (st) {
    return (
      <div className="text-[14px] font-semibold text-ink">
        {st.name} State<span className="ml-2 text-[12px] font-normal text-ink-3">{st.zone}</span>
      </div>
    );
  }
  const label = path.startsWith("/national") ? "National Command Centre" : path === "/about" ? "Method" : "All states";
  return (
    <div className="text-[14px] font-semibold text-ink">
      {label}<span className="ml-2 text-[12px] font-normal text-ink-3">{states.length} states, all six zones</span>
    </div>
  );
}
