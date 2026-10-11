"use server";
import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { ApiError, apiSend } from "@/lib/api";
import { ACTING_COOKIE, actingPerson } from "@/lib/acting";

export type Result<T = any> = { ok: true; data?: T } | { ok: false; error: string };

/** Run one write as the acting person. Errors from the API (including "outside this view") come back as text for the screen. */
async function run<T>(fn: (actor: string) => Promise<T>): Promise<Result<T>> {
  try {
    const p = await actingPerson();
    const data = await fn(p.person_id);
    revalidatePath("/", "layout");
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: e instanceof ApiError ? e.message.replace(/^API \d+ on [^:]+: /, "") : String(e) };
  }
}

export async function caseAction(caseId: string, action: "acknowledge" | "assign" | "advance" | "resolve" | "close" | "note", extra: Record<string, unknown> = {}): Promise<Result> {
  return run((actor) => apiSend("POST", `/cases/${caseId}/${action}`, { actor_person_id: actor, ...extra }));
}

export async function bulkAction(body: { action: string; case_ids?: string[]; person_id?: string; playbook?: string; facility_ids?: string[] }): Promise<Result> {
  return run((actor) => apiSend("POST", "/cases/bulk", { actor_person_id: actor, ...body }));
}

export async function approveMessages(messageIds: string[]): Promise<Result> {
  return run((actor) => apiSend("POST", "/messages/approve", { actor_person_id: actor, message_ids: messageIds }));
}

export async function editMessage(messageId: string, body: string): Promise<Result> {
  return run((actor) => apiSend("POST", `/messages/${messageId}/edit`, { actor_person_id: actor, body }));
}

export async function reviewResponse(responseId: string, opts: { corrected_text?: string; dismiss?: boolean }): Promise<Result> {
  return run((actor) => apiSend("POST", `/responses/${responseId}/review`, { actor_person_id: actor, ...opts }));
}

export async function sendReply(caseId: string, text: string, messageId?: string): Promise<Result> {
  return run((actor) => apiSend("POST", `/cases/${caseId}/reply`, { actor_person_id: actor, text, message_id: messageId }));
}

export async function openFacilityCase(code: string, facilityId: string, playbook?: string, ruleId?: string): Promise<Result> {
  return run((actor) => apiSend("POST", `/state/${code}/facility/${facilityId}/cases`, { actor_person_id: actor, playbook, rule_id: ruleId }));
}

export async function approveResupply(requestId: string): Promise<Result> {
  return run((actor) => apiSend("POST", `/resupply-requests/${requestId}/approve`, { actor_person_id: actor }));
}

export async function requestStateResponse(code: string): Promise<Result> {
  return run((actor) => apiSend("POST", `/national/states/${code}/request-response`, { actor_person_id: actor }));
}

export async function tickClock(days: number): Promise<Result> {
  try { await apiSend("POST", "/sim/tick", { days }); revalidatePath("/", "layout"); return { ok: true }; }
  catch (e) { return { ok: false, error: e instanceof ApiError ? e.message : String(e) }; }
}

export async function resetSimulation(): Promise<Result> {
  try { await apiSend("POST", "/sim/reset?seed_demo=true"); revalidatePath("/", "layout"); return { ok: true }; }
  catch (e) { return { ok: false, error: e instanceof ApiError ? e.message : String(e) }; }
}

export async function setActing(personId: string): Promise<void> {
  (await cookies()).set(ACTING_COOKIE, personId, { path: "/", maxAge: 60 * 60 * 24 * 365, sameSite: "lax" });
  revalidatePath("/", "layout");
}
