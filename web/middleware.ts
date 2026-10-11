import { NextRequest, NextResponse } from "next/server";
import { COOKIE, homeOf, parseScope, pathAllowed } from "@/lib/scopeCore";

/** Keeps each "View as" inside its own pages (the API enforces the same limits). National may open anything. */
export function middleware(req: NextRequest) {
  const scope = parseScope(req.cookies.get(COOKIE)?.value);
  const { pathname } = req.nextUrl;
  if (/\.[a-z0-9]+$/i.test(pathname)) return NextResponse.next();          // files (icons, images)
  if (pathname === "/" && scope.level !== "national") return NextResponse.redirect(new URL(homeOf(scope), req.url));
  if (pathname !== "/" && !pathAllowed(scope, pathname)) return NextResponse.redirect(new URL(homeOf(scope), req.url));
  const headers = new Headers(req.headers);
  const m = pathname.match(/^\/state\/([^/]+)/);
  if (m) headers.set("x-phc-state", m[1]); else headers.delete("x-phc-state");
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: ["/((?!_next|api).*)"] };
