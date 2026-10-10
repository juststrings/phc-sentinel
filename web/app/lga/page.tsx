import { redirect } from "next/navigation";
import { api } from "@/lib/api";

// /lga has no content of its own: open the LGA that needs attention most.
export default async function LgaIndex({ searchParams }: { searchParams: Promise<{ month?: string }> }) {
  const { month } = await searchParams;
  const s = await api("/state/summary", month);
  redirect(`/lga/${s.lgas[0].lga_id}${month ? `?month=${month}` : ""}`);
}
