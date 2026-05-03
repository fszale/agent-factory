import { describe, it, expect } from "vitest";
import { classifyTwinStatus, isStale, relativeTime, statusToBadge } from "@/lib/agent-factory/status";

const NOW = new Date("2026-04-10T12:00:00.000Z");

describe("classifyTwinStatus", () => {
  it("inactive twins are stopped regardless of reported status", () => {
    expect(
      classifyTwinStatus(
        { status: "running", active: false, last_activity_at: NOW.toISOString() },
        NOW,
      ),
    ).toBe("stopped");
  });

  it("error status passes through", () => {
    expect(
      classifyTwinStatus({ status: "error", active: true, last_activity_at: null }, NOW),
    ).toBe("error");
  });

  it("installing status passes through", () => {
    expect(
      classifyTwinStatus({ status: "installing", active: true, last_activity_at: null }, NOW),
    ).toBe("installing");
  });

  it("running status passes through", () => {
    expect(
      classifyTwinStatus(
        { status: "running", active: true, last_activity_at: NOW.toISOString() },
        NOW,
      ),
    ).toBe("running");
  });

  it("idle but recent activity is treated as running", () => {
    const recent = new Date(NOW.getTime() - 5 * 60_000).toISOString();
    expect(
      classifyTwinStatus({ status: "idle", active: true, last_activity_at: recent }, NOW),
    ).toBe("running");
  });

  it("idle with stale activity stays idle", () => {
    const stale = new Date(NOW.getTime() - 2 * 60 * 60_000).toISOString();
    expect(
      classifyTwinStatus({ status: "idle", active: true, last_activity_at: stale }, NOW),
    ).toBe("idle");
  });

  it("unknown status falls back to activity-based classification", () => {
    const recent = new Date(NOW.getTime() - 60_000).toISOString();
    expect(
      classifyTwinStatus({ status: "unknown", active: true, last_activity_at: recent }, NOW),
    ).toBe("running");

    const stale = new Date(NOW.getTime() - 24 * 60 * 60_000).toISOString();
    expect(
      classifyTwinStatus({ status: "unknown", active: true, last_activity_at: stale }, NOW),
    ).toBe("idle");

    expect(
      classifyTwinStatus({ status: "unknown", active: true, last_activity_at: null }, NOW),
    ).toBe("unknown");
  });
});

describe("isStale", () => {
  it("missing or invalid timestamps are stale", () => {
    expect(isStale(null, NOW)).toBe(true);
    expect(isStale(undefined, NOW)).toBe(true);
    expect(isStale("not-a-date", NOW)).toBe(true);
  });

  it("recent timestamps are fresh", () => {
    const t = new Date(NOW.getTime() - 5 * 60_000).toISOString();
    expect(isStale(t, NOW)).toBe(false);
  });

  it("timestamps older than threshold are stale", () => {
    const t = new Date(NOW.getTime() - 2 * 60 * 60_000).toISOString();
    expect(isStale(t, NOW)).toBe(true);
  });
});

describe("statusToBadge", () => {
  it("maps each status to a label/tone", () => {
    expect(statusToBadge("running")).toEqual({ label: "Running", tone: "ok" });
    expect(statusToBadge("idle").tone).toBe("muted");
    expect(statusToBadge("error").tone).toBe("danger");
    expect(statusToBadge("stopped").tone).toBe("muted");
    expect(statusToBadge("installing").tone).toBe("info");
    expect(statusToBadge("unknown").tone).toBe("warn");
  });
});

describe("relativeTime", () => {
  it("formats common ranges", () => {
    expect(relativeTime(null, NOW)).toBe("—");
    expect(relativeTime(NOW.toISOString(), NOW)).toMatch(/just now|0s ago/);
    expect(relativeTime(new Date(NOW.getTime() - 30 * 1000).toISOString(), NOW)).toBe("30s ago");
    expect(relativeTime(new Date(NOW.getTime() - 5 * 60_000).toISOString(), NOW)).toBe("5m ago");
    expect(relativeTime(new Date(NOW.getTime() - 3 * 60 * 60_000).toISOString(), NOW)).toBe("3h ago");
    expect(relativeTime(new Date(NOW.getTime() - 2 * 24 * 60 * 60_000).toISOString(), NOW)).toBe("2d ago");
  });
});
