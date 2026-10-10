import { notFound, redirect } from "next/navigation";
import { apiOrNull } from "@/lib/api";

/** Old single-state URL: forward to the state-scoped LGA page. */
export default async function LegacyLga({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ month?: string; tab?: string }> }) {
  const { id } = await params;
  const { month, tab } = await searchParams;
  const d = await apiOrNull(`/lga/${id}/queue`, month);
  if (!d) notFound();
  const q = new URLSearchParams({ ...(month ? { month } : {}), ...(tab ? { tab } : {}) }).toString();
  redirect(`/state/${d.state.code}/lga/${id}${q ? `?${q}` : ""}`);
}
