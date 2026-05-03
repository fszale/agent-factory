import type { Twin, TwinStatus } from "./types";

export interface StatusBadge {
  label: string;
  tone: "ok" | "warn" | "danger" | "muted" | "info";
}

const STALE_MINUTES = 60;

export function classifyTwinStatus(twin: Pick<Twin, "status" | "active" | "last_activity_at">, now: Date = new Date()): TwinStatus {
  if (!twin.active) return "stopped";
  if (twin.status === "error") return "error";
  if (twin.status === "installing") return "installing";
  if (twin.status === "stopped") return "stopped";
  if (twin.status === "running") return "running";
  if (twin.status === "idle") {
    if (isStale(twin.last_activity_at, now)) return "idle";
    return "running";
  }
  if (twin.last_activity_at) {
    return isStale(twin.last_activity_at, now) ? "idle" : "running";
  }
  return "unknown";
}

export function isStale(lastActivityIso: string | null | undefined, now: Date = new Date()): boolean {
  if (!lastActivityIso) return true;
  const last = Date.parse(lastActivityIso);
  if (Number.isNaN(last)) return true;
  const diffMin = (now.getTime() - last) / 60000;
  return diffMin > STALE_MINUTES;
}

export function statusToBadge(status: TwinStatus): StatusBadge {
  switch (status) {
    case "running":
      return { label: "Running", tone: "ok" };
    case "idle":
      return { label: "Idle", tone: "muted" };
    case "error":
      return { label: "Error", tone: "danger" };
    case "stopped":
      return { label: "Stopped", tone: "muted" };
    case "installing":
      return { label: "Installing", tone: "info" };
    case "unknown":
    default:
      return { label: "Unknown", tone: "warn" };
  }
}

export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const diffSec = Math.round((now.getTime() - t) / 1000);
  if (diffSec < 0) return "just now";
  if (diffSec < 45) return `${diffSec}s ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  const diffMo = Math.round(diffDay / 30);
  if (diffMo < 12) return `${diffMo}mo ago`;
  const diffYr = Math.round(diffMo / 12);
  return `${diffYr}y ago`;
}
