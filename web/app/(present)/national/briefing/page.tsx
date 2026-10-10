import type { Metadata } from "next";
import Briefing from "@/components/national/Briefing";
import { api } from "@/lib/api";

export const metadata: Metadata = { title: "National briefing" };

/** Briefing mode: own layout (no navigation bar); the simulated-data banner comes from the root layout. */
export default async function BriefingPage({ searchParams }: { searchParams: Promise<{ month?: string; slide?: string }> }) {
  const sp = await searchParams;
  const meta = await api("/meta/months");
  const month = sp.month ?? meta.latest;
  const [summary, st, geo] = await Promise.all([api("/national/summary", month), api("/national/states", month), api("/national/geo")]);
  return <Briefing summary={summary} states={st.states} geo={geo} initialSlide={Number(sp.slide ?? 1) - 1} />;
}
