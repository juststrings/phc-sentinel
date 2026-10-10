import { notFound, redirect } from "next/navigation";
import { apiOrNull } from "@/lib/api";

/** Old single-state URL: forward to the state-scoped facility page. */
export default async function LegacyFacility({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ month?: string }> }) {
  const { id } = await params;
  const { month } = await searchParams;
  const d = await apiOrNull(`/facility/${id}`, month);
  if (!d) notFound();
  redirect(`/state/${d.state.code}/facility/${id}${month ? `?month=${month}` : ""}`);
}
