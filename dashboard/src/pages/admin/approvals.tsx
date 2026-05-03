import { useEffect, useMemo, useState } from "react";
import { Check, X, RefreshCcw, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useFactoryQuery } from "@/hooks/use-factory-query";
import { useCredentials } from "@/components/admin/credentials-context";
import { ErrorState } from "@/components/admin/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import {
  applyOptimisticDecision,
  countByStatus,
  revertOptimisticDecision,
} from "@/lib/agent-factory/approvals";
import { relativeTime } from "@/lib/agent-factory/status";
import type { ApprovalItem, ApprovalStatus, Paginated } from "@/lib/agent-factory/types";

const PAGE_SIZE = 50;

export default function AdminApprovals() {
  const { client } = useCredentials();
  const { toast } = useToast();
  const [tab, setTab] = useState<ApprovalStatus>("pending");

  const { data, error, isLoading, refetch } = useFactoryQuery<Paginated<ApprovalItem>>(
    (c, signal) => c.listApprovals({ status: tab, page: 1, page_size: PAGE_SIZE }, { signal }),
    [tab],
    { pollMs: 20000 },
  );

  const [items, setItems] = useState<ApprovalItem[]>([]);
  useEffect(() => {
    setItems(data?.items ?? []);
  }, [data]);

  const counts = useMemo(() => countByStatus(items), [items]);
  const [busy, setBusy] = useState<string | null>(null);
  const [notesById, setNotesById] = useState<Record<string, string>>({});

  const decide = async (item: ApprovalItem, decision: "approved" | "rejected") => {
    if (!client) return;
    const notes = notesById[item.id]?.trim() || undefined;
    const previous = item;
    let next: ApprovalItem[];
    try {
      next = applyOptimisticDecision(items, item.id, decision, { notes, decidedBy: "operator" });
    } catch (err) {
      toast({ title: "Cannot decide", description: (err as Error).message, variant: "destructive" });
      return;
    }
    setItems(next);
    setBusy(item.id);
    try {
      if (decision === "approved") await client.approveApproval(item.id, notes ? { notes } : {});
      else await client.rejectApproval(item.id, notes ? { notes } : {});
      toast({
        title: decision === "approved" ? "Approved" : "Rejected",
        description: item.summary,
      });
      setNotesById((prev) => {
        const copy = { ...prev };
        delete copy[item.id];
        return copy;
      });
    } catch (err) {
      setItems((current) => revertOptimisticDecision(current, previous));
      toast({
        title: "Decision failed",
        description: (err as Error).message,
        variant: "destructive",
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">HITL Approvals</h1>
          <p className="text-sm text-muted-foreground font-mono mt-1">
            Human-in-the-loop checkpoints from twins waiting for your call.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isLoading} data-testid="approvals-refresh">
          <RefreshCcw className={`h-3.5 w-3.5 mr-1 ${isLoading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </header>

      <Tabs value={tab} onValueChange={(v) => setTab(v as ApprovalStatus)}>
        <TabsList>
          <TabsTrigger value="pending" data-testid="approvals-tab-pending">
            Pending {tab === "pending" ? `(${counts.pending})` : ""}
          </TabsTrigger>
          <TabsTrigger value="approved" data-testid="approvals-tab-approved">
            Approved
          </TabsTrigger>
          <TabsTrigger value="rejected" data-testid="approvals-tab-rejected">
            Rejected
          </TabsTrigger>
        </TabsList>

        <TabsContent value={tab} className="mt-4 flex flex-col gap-3">
          {error ? <ErrorState error={error} onRetry={refetch} context="Loading approvals" /> : null}

          {!error && isLoading && items.length === 0 && (
            <>
              {[0, 1].map((i) => (
                <Card key={i}>
                  <CardContent className="p-6">
                    <Skeleton className="h-20 w-full" />
                  </CardContent>
                </Card>
              ))}
            </>
          )}

          {!error && !isLoading && items.length === 0 && (
            <Card>
              <CardContent className="p-8 text-center flex flex-col items-center gap-3">
                <ShieldCheck className="h-10 w-10 text-muted-foreground" />
                <p className="text-sm text-muted-foreground font-mono">No {tab} approvals.</p>
              </CardContent>
            </Card>
          )}

          {items.map((item) => (
            <Card key={item.id} data-testid={`approval-card-${item.id}`}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <CardTitle className="text-base">{item.action}</CardTitle>
                    <CardDescription className="font-mono text-xs">
                      Twin: {item.twin_name ?? item.twin_id} · {relativeTime(item.created_at)}
                    </CardDescription>
                  </div>
                  <span
                    className="text-[11px] font-mono px-2 py-0.5 rounded-full border bg-secondary text-secondary-foreground"
                    data-testid={`approval-status-${item.id}`}
                  >
                    {item.status}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <p className="text-sm">{item.summary}</p>
                {item.payload && Object.keys(item.payload).length > 0 && (
                  <pre className="bg-secondary/40 rounded p-3 text-xs font-mono overflow-x-auto">
                    {JSON.stringify(item.payload, null, 2)}
                  </pre>
                )}
                {item.status === "pending" ? (
                  <>
                    <Textarea
                      placeholder="Notes (optional, attached to your decision)"
                      value={notesById[item.id] ?? ""}
                      onChange={(e) =>
                        setNotesById((prev) => ({ ...prev, [item.id]: e.target.value }))
                      }
                      data-testid={`approval-notes-${item.id}`}
                      rows={2}
                    />
                    <div className="flex gap-2 justify-end">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy === item.id}
                        onClick={() => void decide(item, "rejected")}
                        data-testid={`approval-reject-${item.id}`}
                      >
                        <X className="h-3.5 w-3.5 mr-1" /> Reject
                      </Button>
                      <Button
                        size="sm"
                        disabled={busy === item.id}
                        onClick={() => void decide(item, "approved")}
                        data-testid={`approval-approve-${item.id}`}
                      >
                        <Check className="h-3.5 w-3.5 mr-1" /> Approve
                      </Button>
                    </div>
                  </>
                ) : (
                  <div className="text-xs font-mono text-muted-foreground">
                    Decided {item.decided_at ? relativeTime(item.decided_at) : "—"}
                    {item.decided_by ? ` by ${item.decided_by}` : ""}
                    {item.notes ? ` — ${item.notes}` : ""}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </TabsContent>
      </Tabs>
    </>
  );
}
