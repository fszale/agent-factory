import type {
  ApprovalDecisionRequest,
  ApprovalItem,
  AuditEntry,
  ImportTwinRequest,
  Paginated,
  Thread,
  ThreadMessage,
  Twin,
} from "./types";
import { normalizeBaseUrl } from "./auth";

export class FactoryApiError extends Error {
  status: number;
  code: string;
  body?: unknown;

  constructor(opts: { status: number; code: string; message: string; body?: unknown }) {
    super(opts.message);
    this.name = "FactoryApiError";
    this.status = opts.status;
    this.code = opts.code;
    this.body = opts.body;
  }
}

export interface FactoryClientOptions {
  baseUrl: string;
  apiKey: string;
  fetchImpl?: typeof fetch;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
}

export class FactoryClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: FactoryClientOptions) {
    if (!opts.baseUrl) throw new Error("FactoryClient: baseUrl is required");
    if (!opts.apiKey) throw new Error("FactoryClient: apiKey is required");
    this.baseUrl = normalizeBaseUrl(opts.baseUrl);
    this.apiKey = opts.apiKey.trim();
    this.fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  async request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
    const url = this.buildUrl(path, opts.query);
    const headers: Record<string, string> = {
      Accept: "application/json",
      "X-API-Key": this.apiKey,
      Authorization: `Bearer ${this.apiKey}`,
    };
    let body: BodyInit | undefined;
    if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.body);
    }

    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        method: opts.method ?? "GET",
        headers,
        body,
        signal: opts.signal,
      });
    } catch (err) {
      throw new FactoryApiError({
        status: 0,
        code: "network_error",
        message: err instanceof Error ? err.message : "Network request failed",
      });
    }

    return this.parseResponse<T>(response);
  }

  private buildUrl(path: string, query?: RequestOptions["query"]): string {
    const cleanPath = path.startsWith("/") ? path : `/${path}`;
    const url = new URL(`${this.baseUrl}${cleanPath}`);
    if (query) {
      for (const [k, v] of Object.entries(query)) {
        if (v === undefined || v === null || v === "") continue;
        url.searchParams.set(k, String(v));
      }
    }
    return url.toString();
  }

  private async parseResponse<T>(response: Response): Promise<T> {
    let body: unknown = undefined;
    const text = await response.text();
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }

    if (response.ok) {
      return body as T;
    }

    const code = errorCodeForStatus(response.status);
    const message = extractErrorMessage(body) ?? defaultMessageForStatus(response.status);
    throw new FactoryApiError({
      status: response.status,
      code,
      message,
      body,
    });
  }

  // ---- Twins ----
  listTwins(opts?: { signal?: AbortSignal }): Promise<Twin[]> {
    return this.request<Twin[]>("/twins", { signal: opts?.signal });
  }
  getTwin(id: string, opts?: { signal?: AbortSignal }): Promise<Twin> {
    return this.request<Twin>(`/twins/${encodeURIComponent(id)}`, { signal: opts?.signal });
  }
  importTwin(req: ImportTwinRequest): Promise<Twin> {
    return this.request<Twin>("/twins/import", { method: "POST", body: req });
  }
  setTwinActive(id: string, active: boolean): Promise<Twin> {
    return this.request<Twin>(`/twins/${encodeURIComponent(id)}/active`, {
      method: "PATCH",
      body: { active },
    });
  }
  serveTwin(id: string): Promise<Twin> {
    return this.request<Twin>(`/twins/${encodeURIComponent(id)}/serve`, { method: "POST" });
  }
  stopTwin(id: string): Promise<Twin> {
    return this.request<Twin>(`/twins/${encodeURIComponent(id)}/stop`, { method: "POST" });
  }

  // ---- Threads ----
  listThreads(
    query?: { twin_id?: string; page?: number; page_size?: number },
    opts?: { signal?: AbortSignal },
  ): Promise<Paginated<Thread>> {
    return this.request<Paginated<Thread>>("/threads", { query, signal: opts?.signal });
  }
  getThreadMessages(threadId: string, opts?: { signal?: AbortSignal }): Promise<ThreadMessage[]> {
    return this.request<ThreadMessage[]>(`/threads/${encodeURIComponent(threadId)}/messages`, {
      signal: opts?.signal,
    });
  }

  // ---- HITL Approvals ----
  listApprovals(
    query?: { status?: string; page?: number; page_size?: number },
    opts?: { signal?: AbortSignal },
  ): Promise<Paginated<ApprovalItem>> {
    return this.request<Paginated<ApprovalItem>>("/approvals", { query, signal: opts?.signal });
  }
  approveApproval(id: string, body: ApprovalDecisionRequest = {}): Promise<ApprovalItem> {
    return this.request<ApprovalItem>(`/approvals/${encodeURIComponent(id)}/accept`, {
      method: "POST",
      body,
    });
  }
  rejectApproval(id: string, body: ApprovalDecisionRequest = {}): Promise<ApprovalItem> {
    return this.request<ApprovalItem>(`/approvals/${encodeURIComponent(id)}/reject`, {
      method: "POST",
      body,
    });
  }

  // ---- Audit ----
  listAudit(
    query?: {
      twin_id?: string;
      action?: string;
      start?: string;
      end?: string;
      page?: number;
      page_size?: number;
    },
    opts?: { signal?: AbortSignal },
  ): Promise<Paginated<AuditEntry>> {
    return this.request<Paginated<AuditEntry>>("/audit", { query, signal: opts?.signal });
  }
}

export function errorCodeForStatus(status: number): string {
  if (status === 0) return "network_error";
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422) return "unprocessable_entity";
  if (status === 429) return "rate_limited";
  if (status >= 500 && status < 600) return "server_error";
  if (status >= 400 && status < 500) return "client_error";
  return "unknown";
}

export function defaultMessageForStatus(status: number): string {
  switch (status) {
    case 401:
      return "API key was rejected. Open Settings and verify the key.";
    case 403:
      return "Forbidden: this API key does not have access.";
    case 404:
      return "Resource not found.";
    case 409:
      return "Conflict with the current state.";
    case 422:
      return "Request was rejected as invalid.";
    case 429:
      return "Rate limited. Try again in a moment.";
    default:
      if (status >= 500) return `Server error (${status}).`;
      return `Request failed with status ${status}.`;
  }
}

export function extractErrorMessage(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const obj = body as Record<string, unknown>;
  if (typeof obj.detail === "string") return obj.detail;
  if (typeof obj.message === "string") return obj.message;
  if (typeof obj.error === "string") return obj.error;
  if (Array.isArray(obj.detail) && obj.detail.length > 0) {
    const first = obj.detail[0] as Record<string, unknown>;
    if (typeof first?.msg === "string") return first.msg;
  }
  return null;
}
