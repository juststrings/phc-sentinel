"use client";
import { usePathname } from "next/navigation";
import type { StateInfo } from "./Sidebar";
import { useStateCode } from "./Sidebar";

/** Top-bar label: the state (and zone) being viewed, or the national scope. */
export default function ScopeLabel({ states }: { states: StateInfo[] }) {
  const path = usePathname();
  const code = useStateCode();
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
