"use client";
import { useRouter, useSearchParams } from "next/navigation";

export type StateOpt = { code: string; name: string; zone: string };
const SUFFIX = { overview: "", lga: "/lga", facilities: "/facilities" } as const;

/** Switch state without leaving the current view (overview, LGA queues or facilities). Hidden inside the States modal,
 *  where the state is fixed (the .shell-chrome class is hidden in the embedded frame). */
export default function StateSelect({ states, value, view, className = "" }: {
  states: StateOpt[]; value: string; view: keyof typeof SUFFIX; className?: string;
}) {
  const router = useRouter();
  const month = useSearchParams().get("month");
  const zones = [...new Set(states.map((s) => s.zone))];
  return (
    <label className={`shell-chrome flex flex-col gap-1 text-[12px] text-ink-3 ${className}`}>
      State
      <select
        aria-label="State"
        value={value}
        onChange={(e) => router.push(`/state/${e.target.value}${SUFFIX[view]}${month ? `?month=${month}` : ""}`)}
        className="rounded border border-line bg-card px-3 py-2 text-[14px] font-semibold text-ink"
      >
        {zones.map((z) => (
          <optgroup key={z} label={z}>
            {states.filter((s) => s.zone === z).map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </optgroup>
        ))}
      </select>
    </label>
  );
}
