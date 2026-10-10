import { NextRequest, NextResponse } from "next/server";
import { api } from "@/lib/api";

// Server-side proxy so the browser never needs to reach the API host directly.
export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") ?? "";
  if (q.trim().length < 2) return NextResponse.json([]);
  const r = await api<any>(`/facilities?q=${encodeURIComponent(q)}&page_size=8`);
  return NextResponse.json(
    r.facilities.map((f: any) => ({ facility_id: f.facility_id, name: f.name, lga: f.lga, ward: f.ward })),
  );
}
