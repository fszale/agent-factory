import { describe, it, expect } from "vitest";
import {
  applyDecision,
  applyOptimisticDecision,
  canTransition,
  countByStatus,
  InvalidApprovalTransitionError,
  revertOptimisticDecision,
} from "@/lib/agent-factory/approvals";
import type { ApprovalItem } from "@/lib/agent-factory/types";

const baseItem: ApprovalItem = {
  id: "a1",
  twin_id: "t1",
  twin_name: "Sales Twin",
  thread_id: "thr1",
  action: "send.email",
  summary: "Send quote",
  payload: { to: "buyer@example.com" },
  status: "pending",
  created_at: "2026-04-01T10:00:00.000Z",
  decided_at: null,
  decided_by: null,
  notes: null,
};

describe("canTransition", () => {
  it("allows pending → approved/rejected", () => {
    expect(canTransition("pending", "approved")).toBe(true);
    expect(canTransition("pending", "rejected")).toBe(true);
  });

  it("disallows transitions out of terminal states", () => {
    expect(canTransition("approved", "rejected")).toBe(false);
    expect(canTransition("rejected", "approved")).toBe(false);
    expect(canTransition("approved", "pending")).toBe(false);
    expect(canTransition("rejected", "pending")).toBe(false);
  });

  it("disallows pending → pending self-loop", () => {
    expect(canTransition("pending", "pending")).toBe(false);
  });
});

describe("applyDecision", () => {
  it("approves a pending item with notes and timestamp", () => {
    const fixedNow = new Date("2026-04-02T08:30:00.000Z");
    const out = applyDecision(baseItem, "approved", {
      notes: "looks fine",
      decidedBy: "filip",
      now: fixedNow,
    });
    expect(out.status).toBe("approved");
    expect(out.notes).toBe("looks fine");
    expect(out.decided_by).toBe("filip");
    expect(out.decided_at).toBe(fixedNow.toISOString());
  });

  it("rejects a pending item", () => {
    const out = applyDecision(baseItem, "rejected", { notes: "no" });
    expect(out.status).toBe("rejected");
    expect(out.notes).toBe("no");
  });

  it("preserves existing notes when none supplied", () => {
    const item: ApprovalItem = { ...baseItem, notes: "preexisting" };
    const out = applyDecision(item, "approved");
    expect(out.notes).toBe("preexisting");
  });

  it("throws InvalidApprovalTransitionError on illegal transitions", () => {
    const approved: ApprovalItem = { ...baseItem, status: "approved" };
    expect(() => applyDecision(approved, "rejected")).toThrow(InvalidApprovalTransitionError);
  });

  it("does not mutate the input item", () => {
    const before = JSON.stringify(baseItem);
    applyDecision(baseItem, "approved", { notes: "x" });
    expect(JSON.stringify(baseItem)).toBe(before);
  });
});

describe("optimistic queue updates", () => {
  const items: ApprovalItem[] = [
    baseItem,
    { ...baseItem, id: "a2", action: "publish.post" },
    { ...baseItem, id: "a3", status: "approved" },
  ];

  it("applies a decision to the matching item only", () => {
    const next = applyOptimisticDecision(items, "a2", "rejected", { notes: "no" });
    expect(next[0].status).toBe("pending");
    expect(next[1].status).toBe("rejected");
    expect(next[1].notes).toBe("no");
    expect(next[2].status).toBe("approved");
  });

  it("revert restores the original item", () => {
    const optimistic = applyOptimisticDecision(items, "a1", "approved");
    expect(optimistic[0].status).toBe("approved");
    const reverted = revertOptimisticDecision(optimistic, items[0]);
    expect(reverted[0]).toEqual(items[0]);
  });

  it("propagates transition errors when an illegal id is targeted", () => {
    expect(() =>
      applyOptimisticDecision(items, "a3", "rejected"),
    ).toThrow(InvalidApprovalTransitionError);
  });
});

describe("countByStatus", () => {
  it("counts items grouped by status", () => {
    const counts = countByStatus([
      baseItem,
      { ...baseItem, id: "a2", status: "approved" },
      { ...baseItem, id: "a3", status: "approved" },
      { ...baseItem, id: "a4", status: "rejected" },
    ]);
    expect(counts).toEqual({ pending: 1, approved: 2, rejected: 1 });
  });

  it("returns zeros for an empty input", () => {
    expect(countByStatus([])).toEqual({ pending: 0, approved: 0, rejected: 0 });
  });
});
