import { notFound, redirect } from "next/navigation";
import { apiOrNull } from "@/lib/api";

// /state/{code}/lga has no content of its own: open the state's LGA that needs attention most.
export default async function LgaIndex({ params, searchParams }: { params: Promise<{ code: string }>; searchParams: Promise<{ month?: string }> }) {
  const { code } = await params;
  const { month } = await searchParams;
  const s = await apiOrNull(`/state/${code}/summary`, month);
  if (!s) notFound();
  redirect(`/state/${code}/lga/${s.lgas[0].lga_id}${month ? `?month=${month}` : ""}`);
}
