export type TwinStatus =
  | "running"
  | "idle"
  | "error"
  | "stopped"
  | "installing"
  | "unknown";

export interface Twin {
  id: string;
  name: string;
  description?: string | null;
  model: string;
  status: TwinStatus;
  active: boolean;
  last_activity_at?: string | null;
  installed_at?: string | null;
  source_url?: string | null;
  version?: string | null;
}

export interface Thread {
  id: string;
  twin_id: string;
  twin_name?: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_run_status?: RunStatus | null;
}

export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "awaiting_approval";

export interface ThreadMessage {
  id: string;
  thread_id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  created_at: string;
  run_id?: string | null;
  model?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  status?: RunStatus | null;
}

export type ApprovalStatus = "pending" | "approved" | "rejected";

export interface ApprovalItem {
  id: string;
  twin_id: string;
  twin_name?: string;
  thread_id?: string | null;
  action: string;
  summary: string;
  payload?: Record<string, unknown> | null;
  status: ApprovalStatus;
  created_at: string;
  decided_at?: string | null;
  decided_by?: string | null;
  notes?: string | null;
}

export type AuditAction =
  | "twin.install"
  | "twin.uninstall"
  | "twin.activate"
  | "twin.deactivate"
  | "twin.serve"
  | "twin.stop"
  | "thread.create"
  | "run.start"
  | "run.complete"
  | "run.fail"
  | "approval.request"
  | "approval.accept"
  | "approval.reject"
  | "config.change"
  | string;

export interface AuditEntry {
  id: string;
  created_at: string;
  twin_id?: string | null;
  twin_name?: string | null;
  action: AuditAction;
  actor: string;
  target?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ImportTwinRequest {
  source_url: string;
  branch?: string;
  active?: boolean;
}

export interface ApprovalDecisionRequest {
  notes?: string;
}
