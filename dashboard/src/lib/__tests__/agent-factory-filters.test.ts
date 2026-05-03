import { describe, it, expect } from "vitest";
import { applyAuditFilter, paginate, clampPage, uniqueValues } from "@/lib/agent-factory/filters";
import type { AuditEntry } from "@/lib/agent-factory/types";

const sample: AuditEntry[] = [
  {
    id: "e1",
    created_at: "2026-04-01T10:00:00.000Z",
    twin_id: "t1",
    twin_name: "Sales",
    action: "twin.install",
    actor: "filip",
    target: null,
    metadata: { source_url: "https://github.com/x/sales" },
  },
  {
    id: "e2",
    created_at: "2026-04-02T11:00:00.000Z",
    twin_id: "t2",
    twin_name: "Ops",
    action: "approval.accept",
    actor: "filip",
    target: "approval-99",
    metadata: { notes: "ok" },
  },
  {
    id: "e3",
    created_at: "2026-04-03T11:00:00.000Z",
    twin_id: "t1",
    twin_name: "Sales",
    action: "run.fail",
    actor: "system",
    target: "run-7",
    metadata: { reason: "timeout connecting to provider" },
  },
  {
    id: "e4",
    created_at: "2026-04-05T08:00:00.000Z",
    twin_id: "t3",
    twin_name: "Marketing",
    action: "twin.deactivate",
    actor: "filip",
    target: null,
    metadata: null,
  },
];

describe("applyAuditFilter", () => {
  it("returns all entries when filter is empty / 'all'", () => {
    expect(applyAuditFilter(sample, {})).toHaveLength(4);
    expect(applyAuditFilter(sample, { twinId: "all", action: "all" })).toHaveLength(4);
  });

  it("filters by twinId", () => {
    const out = applyAuditFilter(sample, { twinId: "t1" });
    expect(out.map((e) => e.id)).toEqual(["e1", "e3"]);
  });

  it("filters by action", () => {
    const out = applyAuditFilter(sample, { action: "approval.accept" });
    expect(out.map((e) => e.id)).toEqual(["e2"]);
  });

  it("filters by inclusive date range (whole-day end)", () => {
    const out = applyAuditFilter(sample, {
      startDate: "2026-04-02",
      endDate: "2026-04-03",
    });
    expect(out.map((e) => e.id)).toEqual(["e2", "e3"]);
  });

  it("respects start without end", () => {
    const out = applyAuditFilter(sample, { startDate: "2026-04-04" });
    expect(out.map((e) => e.id)).toEqual(["e4"]);
  });

  it("free-text searches across action, actor, target, and metadata", () => {
    expect(applyAuditFilter(sample, { search: "timeout" }).map((e) => e.id)).toEqual(["e3"]);
    expect(applyAuditFilter(sample, { search: "FILIP" }).map((e) => e.id)).toEqual([
      "e1",
      "e2",
      "e4",
    ]);
    expect(applyAuditFilter(sample, { search: "marketing" }).map((e) => e.id)).toEqual(["e4"]);
  });

  it("combines filters with AND semantics", () => {
    const out = applyAuditFilter(sample, {
      twinId: "t1",
      action: "run.fail",
      search: "timeout",
    });
    expect(out.map((e) => e.id)).toEqual(["e3"]);
  });

  it("returns no results when filters exclude everything", () => {
    expect(
      applyAuditFilter(sample, { twinId: "t1", action: "approval.accept" }),
    ).toHaveLength(0);
  });
});

describe("paginate", () => {
  const items = Array.from({ length: 23 }, (_, i) => ({ id: i + 1 }));

  it("returns the requested page", () => {
    const out = paginate(items, { page: 1, pageSize: 10 });
    expect(out.items).toHaveLength(10);
    expect(out.items[0].id).toBe(1);
    expect(out.totalPages).toBe(3);
    expect(out.totalItems).toBe(23);
    expect(out.hasPrev).toBe(false);
    expect(out.hasNext).toBe(true);
  });

  it("returns a partial last page", () => {
    const out = paginate(items, { page: 3, pageSize: 10 });
    expect(out.items).toHaveLength(3);
    expect(out.items[0].id).toBe(21);
    expect(out.hasPrev).toBe(true);
    expect(out.hasNext).toBe(false);
  });

  it("clamps pages above the maximum to the last page", () => {
    const out = paginate(items, { page: 99, pageSize: 10 });
    expect(out.page).toBe(3);
    expect(out.items).toHaveLength(3);
  });

  it("clamps pages below 1 to the first page", () => {
    const out = paginate(items, { page: 0, pageSize: 10 });
    expect(out.page).toBe(1);
    expect(out.hasPrev).toBe(false);
  });

  it("handles empty inputs", () => {
    const out = paginate<{ id: number }>([], { page: 1, pageSize: 10 });
    expect(out.items).toEqual([]);
    expect(out.totalPages).toBe(1);
    expect(out.totalItems).toBe(0);
    expect(out.hasNext).toBe(false);
    expect(out.hasPrev).toBe(false);
  });
});

describe("clampPage", () => {
  it("clamps to range [1, totalPages]", () => {
    expect(clampPage(0, 5)).toBe(1);
    expect(clampPage(3, 5)).toBe(3);
    expect(clampPage(99, 5)).toBe(5);
    expect(clampPage(NaN, 5)).toBe(1);
    expect(clampPage(2.7, 5)).toBe(2);
  });
});

describe("uniqueValues", () => {
  it("returns unique non-null values", () => {
    expect(uniqueValues(sample, "twin_id").sort()).toEqual(["t1", "t2", "t3"]);
    expect(uniqueValues(sample, "action").sort()).toEqual(
      ["approval.accept", "run.fail", "twin.deactivate", "twin.install"].sort(),
    );
  });
});
