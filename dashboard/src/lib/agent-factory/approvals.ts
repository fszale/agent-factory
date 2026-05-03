import type { ApprovalItem, ApprovalStatus } from "./types";

export type ApprovalDecision = "approved" | "rejected";

const ALLOWED_TRANSITIONS: Record<ApprovalStatus, ApprovalStatus[]> = {
  pending: ["approved", "rejected"],
  approved: [],
  rejected: [],
};

export function canTransition(from: ApprovalStatus, to: ApprovalStatus): boolean {
  return ALLOWED_TRANSITIONS[from]?.includes(to) ?? false;
}

export function applyDecision(
  item: ApprovalItem,
  decision: ApprovalDecision,
  opts: { notes?: string; decidedBy?: string; now?: Date } = {},
): ApprovalItem {
  if (!canTransition(item.status, decision)) {
    throw new InvalidApprovalTransitionError(item.status, decision);
  }
  const now = opts.now ?? new Date();
  return {
    ...item,
    status: decision,
    notes: opts.notes ?? item.notes ?? null,
    decided_at: now.toISOString(),
    decided_by: opts.decidedBy ?? item.decided_by ?? null,
  };
}

export function applyOptimisticDecision(
  items: ApprovalItem[],
  id: string,
  decision: ApprovalDecision,
  opts?: { notes?: string; decidedBy?: string; now?: Date },
): ApprovalItem[] {
  return items.map((item) => (item.id === id ? applyDecision(item, decision, opts) : item));
}

export function revertOptimisticDecision(
  items: ApprovalItem[],
  previous: ApprovalItem,
): ApprovalItem[] {
  return items.map((item) => (item.id === previous.id ? previous : item));
}

export class InvalidApprovalTransitionError extends Error {
  from: ApprovalStatus;
  to: ApprovalStatus;
  constructor(from: ApprovalStatus, to: ApprovalStatus) {
    super(`Cannot transition approval from "${from}" to "${to}"`);
    this.name = "InvalidApprovalTransitionError";
    this.from = from;
    this.to = to;
  }
}

export function countByStatus(items: ApprovalItem[]): Record<ApprovalStatus, number> {
  const out: Record<ApprovalStatus, number> = { pending: 0, approved: 0, rejected: 0 };
  for (const item of items) out[item.status] += 1;
  return out;
}
