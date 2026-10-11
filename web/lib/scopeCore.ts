// The "View as" choice. Pure functions, usable in middleware, server components and client components.
export const COOKIE = "phc_view";

export type Scope =
  | { level: "national" }
  | { level: "state"; state: string }
  | { level: "lga"; state: string; lga: string };

export const NATIONAL: Scope = { level: "national" };

/** Cookie / header form: national | state:<code> | lga:<code>:<lga_id>. Anything else is National. */
export function parseScope(v?: string | null): Scope {
  const p = decodeURIComponent(v ?? "").split(":");
  if (p[0] === "state" && p[1]) return { level: "state", state: p[1] };
  if (p[0] === "lga" && p[1] && p[2]) return { level: "lga", state: p[1], lga: p[2] };
  return NATIONAL;
}

export function scopeHeader(s: Scope): string {
  return s.level === "national" ? "national" : s.level === "state" ? `state:${s.state}` : `lga:${s.state}:${s.lga}`;
}

/** Where each view lands. */
export function homeOf(s: Scope): string {
  return s.level === "national" ? "/national" : s.level === "state" ? `/state/${s.state}` : `/state/${s.state}/lga/${s.lga}`;
}

/** The pages a view may open (the API enforces the same limits; this keeps the interface honest). */
export function pathAllowed(s: Scope, path: string): boolean {
  if (s.level === "national") return true;
  if (path === "/about" || path.startsWith("/cases/") || path === "/me" || path.startsWith("/api/")) return true;
  const own = `/state/${s.state}`;
  if (s.level === "state") return path === own || path.startsWith(own + "/");
  const lga = `${own}/lga/${s.lga}`;
  return path === lga || path.startsWith(lga + "/") || path === `${own}/facilities` || path.startsWith(`${own}/facility/`);
}
