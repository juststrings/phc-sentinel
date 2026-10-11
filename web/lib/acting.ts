import { cookies, headers } from "next/headers";
import { api, apiOrNull } from "./api";
import { getScope } from "./scope";
import type { Scope } from "./scopeCore";

export const ACTING_COOKIE = "phc_acting";

export type Person = {
  person_id: string; name: string; role_code: string; role_title: string; level: string;
  state_code?: string | null; lga_id?: string | null; lga?: string | null; facility?: string | null;
};

/** The synthetic person who leads the chosen view: the national director, a state's Director of PHC, or an LGA's PHC Coordinator. */
export async function leadPerson(scope: Scope): Promise<Person> {
  const qs = scope.level === "national" ? "role=national"
    : scope.level === "state" ? `role=state&state=${scope.state}` : `role=lga&state=${scope.state}&lga=${scope.lga}`;
  return (await api<any>(`/meta/signin?${qs}`)).person;
}

/** Who you are acting as: the person chosen in the Acting-as picker, if they sit inside the view, otherwise the view's lead. */
export async function actingPerson(): Promise<Person> {
  const scope = await getScope();
  const id = (await cookies()).get(ACTING_COOKIE)?.value;
  if (id) {
    try {
      const r = await apiOrNull<any>(`/people/${encodeURIComponent(id)}`);
      const hint = scope.level === "national" ? (await headers()).get("x-phc-state") : null;
      const elsewhere = hint && r?.person && r.person.level !== "national" && r.person.state_code !== hint;     // someone from another state
      if (r?.person && personInScope(r.person, scope) && !elsewhere) return r.person;
    } catch { /* outside the view: fall back to the lead */ }
  }
  if (scope.level === "national") {
    const st = (await headers()).get("x-phc-state");
    if (st) { try { return await leadPerson({ level: "state", state: st }); } catch { /* unknown state: fall back */ } }
  }
  return leadPerson(scope);
}

export function personInScope(p: Person, s: Scope): boolean {
  if (s.level === "national") return true;
  if (p.level === "national" || p.state_code !== s.state) return false;
  return s.level === "state" || (p.lga_id === s.lga && p.level !== "state");
}

/** People you may act as in this view (a short list: leads first). */
export async function actingOptions(scope: Scope): Promise<Person[]> {
  const lead = await actingPerson();
  let rest: Person[] = [];
  const st = scope.level === "national" ? (await headers()).get("x-phc-state") : null;
  if (scope.level === "national" && st) rest = (await api<any>(`/meta/personas?state=${st}`)).personas;
  else if (scope.level === "national") rest = (await api<any>("/meta/personas")).personas;
  else if (scope.level === "state") rest = (await api<any>(`/meta/personas?state=${scope.state}`)).personas;
  else rest = (await api<any>(`/state/${scope.state}/people?lga_id=${scope.lga}&limit=40`)).people;
  const seen = new Set([lead.person_id]);
  return [lead, ...rest.filter((p) => !seen.has(p.person_id) && personInScope(p, scope))];
}
