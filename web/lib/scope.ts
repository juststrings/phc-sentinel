import { cookies } from "next/headers";
import { COOKIE, parseScope, type Scope } from "./scopeCore";

export * from "./scopeCore";

/** The current "View as" choice (server components and route handlers). National when none has been made. */
export async function getScope(): Promise<Scope> {
  return parseScope((await cookies()).get(COOKIE)?.value);
}
