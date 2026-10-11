import { NextRequest, NextResponse } from "next/server";
import { api } from "@/lib/api";

// CSV export of a state's resupply requests (the API checks the view; synthetic data).
export async function GET(req: NextRequest) {
  const state = req.nextUrl.searchParams.get("state") ?? "";
  const r = await api<any>(`/state/${encodeURIComponent(state)}/resupply-requests`);
  const rows: any[] = r.requests;
  const cols = rows.length ? Object.keys(rows[0]) : ["request_id"];
  const esc = (v: unknown) => { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const csv = ["# PHC Sentinel DEMO: synthetic resupply requests, not real orders", cols.join(","), ...rows.map((x) => cols.map((c) => esc(x[c])).join(","))].join("\r\n");
  return new NextResponse(csv, { headers: { "Content-Type": "text/csv", "Content-Disposition": `attachment; filename=sentinel-demo-resupply-${state}.csv` } });
}
