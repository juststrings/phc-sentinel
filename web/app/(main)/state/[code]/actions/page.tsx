import type { Metadata } from "next";
import ActionCentreView from "@/components/actions/ActionCentreView";

export const metadata: Metadata = { title: "Action Centre" };

export default async function StateActions({ params, searchParams }: { params: Promise<{ code: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { code } = await params;
  return <ActionCentreView code={code} sp={await searchParams} />;
}
