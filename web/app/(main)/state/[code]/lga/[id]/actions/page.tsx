import type { Metadata } from "next";
import ActionCentreView from "@/components/actions/ActionCentreView";

export const metadata: Metadata = { title: "LGA Action Centre" };

export default async function LgaActions({ params, searchParams }: { params: Promise<{ code: string; id: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { code, id } = await params;
  return <ActionCentreView code={code} lgaId={id} sp={await searchParams} />;
}
