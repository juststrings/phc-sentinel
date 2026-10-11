"use client";
import { useTransition } from "react";
import { setActing } from "@/app/actions";
import type { Person } from "@/lib/acting";

/** Who you act as inside the chosen view. Cases, approvals and replies are recorded under this person. */
export default function ActingAs({ current, options }: { current: Person; options: Person[] }) {
  const [pending, start] = useTransition();
  return (
    <label className="flex flex-col gap-1 text-[11px] text-ink-3">
      Acting as
      <select
        aria-label="Acting as" value={current.person_id} disabled={pending}
        onChange={(e) => start(() => setActing(e.target.value))}
        className="max-w-[260px] rounded border border-line bg-card px-2 py-1.5 text-[13px] font-medium text-ink"
      >
        {options.map((p) => (
          <option key={p.person_id} value={p.person_id}>{p.name}: {p.role_title}{p.lga ? `, ${p.lga}` : ""}</option>
        ))}
        {!options.some((p) => p.person_id === current.person_id) && <option value={current.person_id}>{current.name}: {current.role_title}</option>}
      </select>
    </label>
  );
}
