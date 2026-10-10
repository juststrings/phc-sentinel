import { CONF_COLOR, SEV_COLOR, STATUS_STYLE, TAG_STYLE } from "@/lib/api";

export function QueueTag({ tag }: { tag: string }) {
  const s = TAG_STYLE[tag] ?? { color: "var(--st-neutral)", label: tag, icon: "•" };
  return (
    <span className="tag" title={s.label}>
      <span aria-hidden style={{ color: s.color, fontSize: 10 }}>{s.icon}</span>
      {s.label}
    </span>
  );
}

export function SevBadge({ sev, muted }: { sev?: string | null; muted?: boolean }) {
  if (!sev) return <span className="muted">n/a</span>;
  return (
    <span className="tag" style={muted ? { opacity: 0.6 } : undefined}>
      <span className="dot" style={{ background: SEV_COLOR[sev] }} />
      {sev.charAt(0) + sev.slice(1).toLowerCase()}
    </span>
  );
}

export function ConfBadge({ conf }: { conf: string }) {
  return (
    <span className="tag">
      <span className="dot" style={{ background: CONF_COLOR[conf], borderRadius: 2 }} />
      {conf.charAt(0) + conf.slice(1).toLowerCase()} confidence
    </span>
  );
}

/** State status for the national view: icon + text on a soft tint, never colour alone. */
export function StatusPill({ status, size }: { status: string; size?: "lg" }) {
  const s = STATUS_STYLE[status] ?? { label: status, icon: "•", color: "var(--st-neutral)", soft: "var(--surface-2)", long: "" };
  return (
    <span className="status-pill" title={s.long}
      style={{ background: s.soft, border: `1px solid color-mix(in srgb, ${s.color} 45%, transparent)`, ...(size === "lg" ? { fontSize: 14, padding: "4px 12px" } : {}) }}>
      <span aria-hidden className="ico" style={{ color: s.color }}>{s.icon}</span>
      {s.label}
    </span>
  );
}

export function SimChip({ text = "Simulated data" }: { text?: string }) {
  return <span className="sim-chip" title="All operational reporting data are simulated"><span aria-hidden>⚠</span>{text}</span>;
}
