import type { Metadata } from "next";
import MessagesView from "@/components/actions/MessagesView";

export const metadata: Metadata = { title: "Messages" };

export default async function LgaMessages({ params, searchParams }: { params: Promise<{ code: string; id: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { code, id } = await params;
  return <MessagesView code={code} lgaId={id} sp={await searchParams} />;
}
