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

// Used by the landing / national / briefing components (legacy styles). The state pages use lib/tokens.ts.
export const QUEUE_LABEL: Record<string, string> = {
  RESOURCE_ACTION: "Resource action",
  DATA_VERIFICATION: "Data verification",
  MONITOR: "Monitor",
};

export const TAG_STYLE: Record<string, { color: string; label: string; icon: string }> = {
  "ACT NOW": { color: "var(--st-critical)", label: "Act now", icon: "▲" },
  "VERIFY THEN ACT": { color: "var(--st-serious)", label: "Verify then act", icon: "◆" },
  "DO NOT ASSUME SAFE": { color: "var(--st-warning)", label: "Do not assume safe", icon: "?" },
  MONITOR: { color: "var(--st-good)", label: "Monitor", icon: "●" },
};

/** State status label (national view). Mirrors the Risk x Confidence matrix at state level;
 * always shown as text + icon, never colour alone. */
export const STATUS_STYLE: Record<string, { label: string; long: string; icon: string; color: string; soft: string }> = {
  act_and_verify: { label: "Act and verify", long: "High action load and a large evidence gap", icon: "▲", color: "var(--st-critical)", soft: "var(--st-critical-soft)" },
  action_load: { label: "High action load", long: "Many PHCs need resupply or repair now", icon: "◆", color: "var(--st-serious)", soft: "var(--st-serious-soft)" },
  evidence_gap: { label: "Evidence gap", long: "Too many PHCs whose calm cannot be trusted", icon: "?", color: "var(--st-warning)", soft: "var(--st-warning-soft)" },
  watch: { label: "Watch", long: "Action load and evidence gap both below the alert thresholds", icon: "●", color: "var(--st-good)", soft: "var(--st-good-soft)" },
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
