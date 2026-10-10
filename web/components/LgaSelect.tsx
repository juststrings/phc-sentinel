"use client";
import { useRouter, useSearchParams } from "next/navigation";

export default function LgaSelect({ lgas, value, code }: { lgas: { lga_id: string; lga: string }[]; value: string; code: string }) {
  const router = useRouter();
  const params = useSearchParams();
  return (
    <label className="flex flex-col gap-1 text-[12px] text-ink-3">
      LGA
    <select
      aria-label="LGA"
      value={value}
      className="rounded border border-line bg-card px-3 py-2 text-[14px] font-semibold text-ink"
      onChange={(e) => {
        const p = new URLSearchParams(params.toString());
        router.push(`/state/${code}/lga/${e.target.value}${p.get("month") ? `?month=${p.get("month")}` : ""}`);
      }}
    >
      {[...lgas].sort((a, b) => a.lga.localeCompare(b.lga)).map((l) => (
        <option key={l.lga_id} value={l.lga_id}>{l.lga}</option>
      ))}
    </select>
    </label>
  );
}
