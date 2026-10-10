import Icon from "./Icon";
import {
  CONF_LABEL, CONF_STYLE, QUEUE_CLASS, RISK_LABEL, RISK_STYLE, queueStyle,
  type Confidence, type Risk,
} from "@/lib/tokens";

const base = "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[12px] font-medium leading-4";

/** The one shared chip. Every state is dual-coded: colour plus icon or text. */
export default function Chip(
  props:
    | { kind: "queue"; tag: string; count?: number }
    | { kind: "risk"; value?: string | null }
    | { kind: "confidence"; value?: string | null },
) {
  if (props.kind === "queue") {
    const s = queueStyle(props.tag);
    return (
      <span className={`${base} border ${QUEUE_CLASS[s.token].chip}`} data-queue-token={s.token}>
        <Icon name={s.icon} size={13} />
        {s.label}
        {props.count != null && <span className="ml-1 font-bold tabular-nums">{props.count}</span>}
      </span>
    );
  }
  if (props.kind === "risk") {
    const key = (props.value ?? "").toUpperCase() as Risk;
    const s = RISK_STYLE[key];
    if (!s) return <span className="text-ink-3">n/a</span>;
    return <span className={base} style={{ background: s.bg, color: s.fg }}>{RISK_LABEL[key]}</span>;
  }
  const key = (props.value ?? "").toUpperCase() as Confidence;
  const s = CONF_STYLE[key];
  if (!s) return <span className="text-ink-3">n/a</span>;
  return <span className={base} style={{ background: s.bg, color: s.fg }}>{CONF_LABEL[key]}</span>;
}
