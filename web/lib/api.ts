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

export const QUEUE_LABEL: Record<string, string> = {
  RESOURCE_ACTION: "Resource action",
  DATA_VERIFICATION: "Data verification",
  MONITOR: "Monitor",
};

// Transitional: legacy pages only. New code uses lib/tokens.ts.
export const TAG_STYLE: Record<string, { color: string; label: string; icon: string }> = {
  "ACT NOW": { color: "var(--q-act)", label: "Act now", icon: "▲" },
  "VERIFY THEN ACT": { color: "var(--q-verify)", label: "Verify then act", icon: "◆" },
  "DO NOT ASSUME SAFE": { color: "var(--q-dnas)", label: "Do not assume safe", icon: "◪" },
  MONITOR: { color: "var(--q-monitor)", label: "Monitor", icon: "●" },
};

export const SEV_COLOR: Record<string, string> = {
  CRITICAL: "var(--st-critical)",
  HIGH: "var(--st-serious)",
  WATCH: "var(--st-warning)",
  NORMAL: "var(--st-good)",
};

export const DOMAIN_LABEL: Record<string, string> = {
  malaria_commodity: "Malaria commodities",
  vaccine_cold_chain: "Vaccine & cold chain",
  service_pressure: "Service pressure",
};

export const CONF_COLOR: Record<string, string> = {
  HIGH: "var(--st-good)",
  MODERATE: "var(--st-warning)",
  LOW: "var(--st-critical)",
};

export function monthLabel(m: string) {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo - 1, 1).toLocaleString("en-GB", { month: "short", year: "numeric" });
}

export function pct(x: number | null | undefined) {
  return x == null ? "n/a" : `${Math.round(x * 100)}%`;
}

export function withMonth(href: string, month?: string) {
  return month ? `${href}${href.includes("?") ? "&" : "?"}month=${month}` : href;
}
