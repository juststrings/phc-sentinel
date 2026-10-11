"use client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { monthLabel } from "@/lib/format";

export default function MonthPicker({ months, latest }: { months: string[]; latest: string }) {
  const router = useRouter();
  const path = usePathname();
  const params = useSearchParams();
  const value = params.get("month") ?? latest;
  return (
    <label className="flex items-center gap-2 text-[13px] text-ink-2">
      <span className="th hidden sm:inline">Analysis month</span>
      <select
        aria-label="Analysis month"
        className="rounded border border-line bg-card px-2 py-1.5 text-[13px] text-ink"
        value={value}
        onChange={(e) => {
          const p = new URLSearchParams(params.toString());
          p.set("month", e.target.value);
          p.delete("page");
          router.push(`${path}?${p.toString()}`);
        }}
      >
        {[...months].reverse().map((m) => (
          <option key={m} value={m}>{monthLabel(m)}</option>
        ))}
      </select>
    </label>
  );
}
