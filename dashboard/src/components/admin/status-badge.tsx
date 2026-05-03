import { cn } from "@/lib/utils";
import type { TwinStatus } from "@/lib/agent-factory/types";
import { statusToBadge } from "@/lib/agent-factory/status";

const TONE_CLASSES: Record<string, string> = {
  ok: "bg-emerald-100 text-emerald-900 border-emerald-300",
  warn: "bg-amber-100 text-amber-900 border-amber-300",
  danger: "bg-rose-100 text-rose-900 border-rose-300",
  muted: "bg-secondary text-secondary-foreground border-border",
  info: "bg-sky-100 text-sky-900 border-sky-300",
};

export function TwinStatusBadge({ status }: { status: TwinStatus }) {
  const badge = statusToBadge(status);
  return (
    <span
      data-testid={`twin-status-${status}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-mono",
        TONE_CLASSES[badge.tone],
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {badge.label}
    </span>
  );
}
