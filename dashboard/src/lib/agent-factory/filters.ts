import type { AuditEntry } from "./types";

export interface AuditFilter {
  twinId?: string | "all";
  action?: string | "all";
  startDate?: string | null;
  endDate?: string | null;
  search?: string;
}

export function applyAuditFilter(
  entries: AuditEntry[],
  filter: AuditFilter,
): AuditEntry[] {
  const startMs = filter.startDate ? Date.parse(filter.startDate) : null;
  const endMs = filter.endDate ? endOfDay(filter.endDate) : null;
  const needle = filter.search?.trim().toLowerCase() ?? "";

  return entries.filter((entry) => {
    if (filter.twinId && filter.twinId !== "all") {
      if (entry.twin_id !== filter.twinId) return false;
    }
    if (filter.action && filter.action !== "all") {
      if (entry.action !== filter.action) return false;
    }
    if (startMs !== null) {
      const t = Date.parse(entry.created_at);
      if (Number.isNaN(t) || t < startMs) return false;
    }
    if (endMs !== null) {
      const t = Date.parse(entry.created_at);
      if (Number.isNaN(t) || t > endMs) return false;
    }
    if (needle) {
      const hay = [
        entry.action,
        entry.actor,
        entry.target ?? "",
        entry.twin_name ?? "",
        entry.twin_id ?? "",
        JSON.stringify(entry.metadata ?? {}),
      ]
        .join(" ")
        .toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });
}

export interface PaginationOptions {
  page: number;
  pageSize: number;
}

export interface PaginationResult<T> {
  items: T[];
  page: number;
  pageSize: number;
  totalPages: number;
  totalItems: number;
  hasPrev: boolean;
  hasNext: boolean;
}

export function paginate<T>(items: T[], opts: PaginationOptions): PaginationResult<T> {
  const pageSize = Math.max(1, Math.floor(opts.pageSize));
  const totalItems = items.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const page = clampPage(opts.page, totalPages);
  const start = (page - 1) * pageSize;
  const end = start + pageSize;
  return {
    items: items.slice(start, end),
    page,
    pageSize,
    totalPages,
    totalItems,
    hasPrev: page > 1,
    hasNext: page < totalPages,
  };
}

export function clampPage(page: number, totalPages: number): number {
  if (!Number.isFinite(page) || page < 1) return 1;
  if (page > totalPages) return totalPages;
  return Math.floor(page);
}

function endOfDay(dateIso: string): number | null {
  const t = Date.parse(dateIso);
  if (Number.isNaN(t)) return null;
  const d = new Date(t);
  d.setHours(23, 59, 59, 999);
  return d.getTime();
}

export function uniqueValues<T, K extends keyof T>(items: T[], key: K): Array<NonNullable<T[K]>> {
  const seen = new Set<NonNullable<T[K]>>();
  for (const item of items) {
    const value = item[key];
    if (value === null || value === undefined) continue;
    seen.add(value as NonNullable<T[K]>);
  }
  return Array.from(seen);
}
