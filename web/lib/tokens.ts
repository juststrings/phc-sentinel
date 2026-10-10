// Single source for queue / risk / confidence styling. The CSS variables live in app/globals.css;
// the hex values here are for places CSS variables cannot reach (MapLibre, Recharts fills).

export type QueueToken = "act-now" | "verify-then-act" | "do-not-assume-safe" | "monitor";
export const QUEUE_TOKENS: QueueToken[] = ["act-now", "verify-then-act", "do-not-assume-safe", "monitor"];

export interface QueueStyle {
  token: QueueToken;
  label: string;
  icon: "warning" | "search" | "eye-off" | "check";
  hex: string;                  // solid colour for dots, bars, map
  hexDark: string;
  hatch: boolean;
}

/** API tag -> token. Anything else is a bug, so lookups throw in tests rather than fall back silently. */
export const QUEUE_BY_TAG: Record<string, QueueStyle> = {
  "ACT NOW": { token: "act-now", label: "Act now", icon: "warning", hex: "#b91c1c", hexDark: "#ef4444", hatch: false },
  "VERIFY THEN ACT": { token: "verify-then-act", label: "Verify then act", icon: "search", hex: "#d97706", hexDark: "#f59e0b", hatch: false },
  "DO NOT ASSUME SAFE": { token: "do-not-assume-safe", label: "Do not assume safe", icon: "eye-off", hex: "#4338ca", hexDark: "#818cf8", hatch: true },
  MONITOR: { token: "monitor", label: "Monitor", icon: "check", hex: "#0d9488", hexDark: "#2dd4bf", hatch: false },
};

export function queueStyle(tag: string): QueueStyle {
  const s = QUEUE_BY_TAG[tag];
  if (!s) throw new Error(`Unknown queue tag: ${tag}`);
  return s;
}

/** Tailwind classes per token (full literal strings so Tailwind's scanner keeps them). */
export const QUEUE_CLASS: Record<QueueToken, { chip: string; text: string; bar: string; card: string }> = {
  "act-now": { chip: "bg-act-now-bg text-act-now border-act-now-bd", text: "text-act-now", bar: "bg-[var(--q-act)]", card: "bg-act-now-bg border-act-now-bd" },
  "verify-then-act": { chip: "bg-verify-then-act-bg text-verify-then-act border-verify-then-act-bd", text: "text-verify-then-act", bar: "bg-[var(--q-verify)]", card: "bg-verify-then-act-bg border-verify-then-act-bd" },
  "do-not-assume-safe": { chip: "bg-do-not-assume-safe-bg text-do-not-assume-safe border-do-not-assume-safe-bd border-dashed hatch", text: "text-do-not-assume-safe", bar: "bg-[var(--q-dnas)] hatch-bar", card: "bg-do-not-assume-safe-bg border-do-not-assume-safe-bd border-dashed hatch" },
  monitor: { chip: "bg-monitor-bg text-monitor border-monitor-bd", text: "text-monitor", bar: "bg-[var(--q-monitor)]", card: "bg-monitor-bg border-monitor-bd" },
};

export type Risk = "CRITICAL" | "HIGH" | "WATCH" | "NORMAL";
export const RISK_LABEL: Record<Risk, string> = { CRITICAL: "Critical", HIGH: "High", WATCH: "Watch", NORMAL: "Normal" };
export const RISK_STYLE: Record<Risk, { bg: string; fg: string; hex: string }> = {
  CRITICAL: { bg: "var(--r-critical-bg)", fg: "var(--r-critical-fg)", hex: "#b91c1c" },
  HIGH: { bg: "var(--r-high-bg)", fg: "var(--r-high-fg)", hex: "#ea580c" },
  WATCH: { bg: "var(--r-watch-bg)", fg: "var(--r-watch-fg)", hex: "#ca8a04" },
  NORMAL: { bg: "var(--r-normal-bg)", fg: "var(--r-normal-fg)", hex: "#94a3b8" },
};

export type Confidence = "HIGH" | "MODERATE" | "LOW";
export const CONF_LABEL: Record<Confidence, string> = { HIGH: "High", MODERATE: "Moderate", LOW: "Low" };
export const CONF_STYLE: Record<Confidence, { bg: string; fg: string; hex: string }> = {
  HIGH: { bg: "var(--c-high-bg)", fg: "var(--c-high-fg)", hex: "#cbd5e1" },
  MODERATE: { bg: "var(--c-mod-bg)", fg: "var(--c-mod-fg)", hex: "#64748b" },
  LOW: { bg: "var(--c-low-bg)", fg: "var(--c-low-fg)", hex: "#4338ca" },
};
