import { describe, expect, it } from "vitest";
import { QUEUE_BY_TAG, QUEUE_CLASS, QUEUE_TOKENS, queueStyle } from "../lib/tokens";

// The four tags the decision engine emits (sentinel/engines/decision.py).
const ENGINE_TAGS = ["ACT NOW", "VERIFY THEN ACT", "DO NOT ASSUME SAFE", "MONITOR"];

describe("queue tokens", () => {
  it("maps every engine tag to exactly one of the four tokens", () => {
    for (const tag of ENGINE_TAGS) expect(QUEUE_TOKENS).toContain(queueStyle(tag).token);
    expect(Object.keys(QUEUE_BY_TAG).sort()).toEqual([...ENGINE_TAGS].sort());
    expect(new Set(ENGINE_TAGS.map((t) => queueStyle(t).token)).size).toBe(4);
  });

  it("has classes for every token", () => {
    for (const t of QUEUE_TOKENS) expect(QUEUE_CLASS[t].chip).toBeTruthy();
  });

  it("rejects unknown tags instead of falling back", () => {
    expect(() => queueStyle("SOMETHING ELSE")).toThrow();
  });

  it("keeps do-not-assume-safe visually distinct: own colour and hatch", () => {
    const dnas = queueStyle("DO NOT ASSUME SAFE");
    expect(dnas.hatch).toBe(true);
    expect(QUEUE_CLASS["do-not-assume-safe"].chip).toContain("hatch");
    for (const other of ["ACT NOW", "VERIFY THEN ACT", "MONITOR"]) {
      expect(queueStyle(other).hex).not.toBe(dnas.hex);
      expect(queueStyle(other).hatch).toBe(false);
    }
  });
});
