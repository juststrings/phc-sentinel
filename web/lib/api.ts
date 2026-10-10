const API = process.env.API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = any>(path: string, month?: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = new URL(path, API);
  if (month) url.searchParams.set("month", month);
  for (const [k, v] of Object.entries(params ?? {})) if (v != null) url.searchParams.set(k, v);
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} on ${path}: ${await res.text()}`);
  return res.json();
}

/** Like api(), but returns null on 404 so pages can render notFound(). */
export async function apiOrNull<T = any>(path: string, month?: string): Promise<T | null> {
  const url = new URL(path, API);
  if (month) url.searchParams.set("month", month);
  const res = await fetch(url, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} on ${path}: ${await res.text()}`);
  return res.json();
}

export const DOMAIN_LABEL: Record<string, string> = {
  malaria_commodity: "Malaria commodities",
  vaccine_cold_chain: "Vaccine & cold chain",
  service_pressure: "Service pressure",
};

/** Map / sort metrics for the national view. `worse` = higher values need more attention. */
export const METRICS: { key: string; label: string; short: string; worse: boolean; fmt: "pct" }[] = [
  { key: "pct_act_now", label: "% Act now", short: "Act now", worse: true, fmt: "pct" },
  { key: "pct_verification", label: "% in Data Verification", short: "Data verification", worse: true, fmt: "pct" },
  { key: "reporting_completeness", label: "Reporting completeness", short: "Reporting", worse: false, fmt: "pct" },
  { key: "pct_stale", label: "% stale stock reports", short: "Stale stock reports", worse: true, fmt: "pct" },
];

export function monthLabel(m: string, long = false) {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo - 1, 1).toLocaleString("en-GB", { month: long ? "long" : "short", year: "numeric" });
}

export function pct(x: number | null | undefined, digits = 0) {
  return x == null ? "n/a" : `${(x * 100).toFixed(digits)}%`;
}

export function int(x: number | null | undefined) {
  return x == null ? "n/a" : Math.round(x).toLocaleString("en-GB");
}

export function withMonth(href: string, month?: string) {
  return month ? `${href}${href.includes("?") ? "&" : "?"}month=${month}` : href;
}

export const stateHref = (code: string, month?: string) => withMonth(`/state/${code}`, month);
export const lgaHref = (code: string, lga: string, month?: string) => withMonth(`/state/${code}/lga/${lga}`, month);
export const facilityHref = (code: string, id: string, month?: string) => withMonth(`/state/${code}/facility/${id}`, month);
