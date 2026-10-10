import Icon from "./Icon";
import { QUEUE_CLASS, type QueueToken } from "@/lib/tokens";

/** State status label (set in settings.yaml: national.status). It mirrors the Risk x Confidence matrix at state level and is
 *  always words plus an icon, drawn in the queue token it resembles: act and verify = act now, high action load = verify then act,
 *  evidence gap = do not assume safe, watch = monitor. */
const STATUS: Record<string, { label: string; long: string; token: QueueToken; icon: string }> = {
  act_and_verify: { label: "Act and verify", long: "High action load and a large evidence gap", token: "act-now", icon: "warning" },
  action_load: { label: "High action load", long: "Many PHCs need resupply or repair now", token: "verify-then-act", icon: "search" },
  evidence_gap: { label: "Evidence gap", long: "Too many PHCs whose calm cannot be trusted", token: "do-not-assume-safe", icon: "eye-off" },
  watch: { label: "Watch", long: "Action load and evidence gap both below the alert thresholds", token: "monitor", icon: "check" },
};

export default function StatusChip({ status }: { status?: string | null }) {
  const s = status ? STATUS[status] : undefined;
  if (!s) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[12px] font-medium leading-4 ${QUEUE_CLASS[s.token].chip}`}
      title={s.long}
      data-queue-token={s.token}
    >
      <Icon name={s.icon} size={13} />
      {s.label}
    </span>
  );
}
