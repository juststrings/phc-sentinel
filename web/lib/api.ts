const API = process.env.API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = any>(path: string, month?: string): Promise<T> {
  const url = new URL(path, API);
  if (month) url.searchParams.set("month", month);
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} on ${path}: ${await res.text()}`);
  return res.json();
}

export const DOMAIN_LABEL: Record<string, string> = {
  malaria_commodity: "Malaria commodities",
  vaccine_cold_chain: "Vaccine & cold chain",
  service_pressure: "Service pressure",
};

export function monthLabel(m: string) {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo - 1, 1).toLocaleString("en-GB", { month: "short", year: "numeric" });
}

export function pct(x: number | null | undefined) {
  return x == null ? "n/a" : `${Math.round(x * 100)}%`;
}
