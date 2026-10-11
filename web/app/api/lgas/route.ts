import { NextRequest, NextResponse } from "next/server";
import { api } from "@/lib/api";

// LGA names for the View-as switcher (names only).
export async function GET(req: NextRequest) {
  const state = req.nextUrl.searchParams.get("state") ?? "";
  if (!state) return NextResponse.json([]);
  const r = await api<any>(`/meta/lgas?state=${encodeURIComponent(state)}`);
  return NextResponse.json(r.lgas);
}
