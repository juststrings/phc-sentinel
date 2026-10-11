import { cookies } from "next/headers";
import { COOKIE, parseScope, scopeHeader } from "./scopeCore";

export * from "./format";

const API = process.env.API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

/** Every API call carries the "View as" choice (the phc_view cookie; National when none), and the API filters by it. */
async function viewHeaders(): Promise<Record<string, string>> {
  try {
    const c = await cookies();
    return { "X-View-As": scopeHeader(parseScope(c.get(COOKIE)?.value)) };
  } catch {
    return { "X-View-As": "national" };            // outside a request (build time)
  }
}

export async function api<T = any>(path: string, month?: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = new URL(path, API);
  if (month) url.searchParams.set("month", month);
  for (const [k, v] of Object.entries(params ?? {})) if (v != null) url.searchParams.set(k, v);
  const res = await fetch(url, { cache: "no-store", headers: await viewHeaders() });
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} on ${path}: ${await res.text()}`);
  return res.json();
}

/** Like api(), but returns null on 404 so pages can render notFound(). */
export async function apiOrNull<T = any>(path: string, month?: string): Promise<T | null> {
  const url = new URL(path, API);
  if (month) url.searchParams.set("month", month);
  const res = await fetch(url, { cache: "no-store", headers: await viewHeaders() });
  if (res.status === 404) return null;
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} on ${path}: ${await res.text()}`);
  return res.json();
}

/** POST/PUT helpers for the Action Centre (server actions and route handlers). */
export async function apiSend<T = any>(method: "POST" | "PUT", path: string, body?: unknown): Promise<T> {
  const url = new URL(path, API);
  const res = await fetch(url, {
    method, cache: "no-store", body: body === undefined ? undefined : JSON.stringify(body),
    headers: { ...(await viewHeaders()), "Content-Type": "application/json" },
  });
  const text = await res.text();
  if (!res.ok) {
    let msg = text;
    try { msg = JSON.parse(text).detail ?? text; } catch { /* not JSON */ }
    throw new ApiError(res.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return text ? JSON.parse(text) : (undefined as T);
}
