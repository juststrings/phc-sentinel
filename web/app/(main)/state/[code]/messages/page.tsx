import type { Metadata } from "next";
import MessagesView from "@/components/actions/MessagesView";

export const metadata: Metadata = { title: "Messages" };

export default async function StateMessages({ params, searchParams }: { params: Promise<{ code: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { code } = await params;
  return <MessagesView code={code} sp={await searchParams} />;
}
