import { Link } from "wouter";
import { Activity, Cpu, RefreshCcw, Square, Play, Eye } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useFactoryQuery } from "@/hooks/use-factory-query";
import { useCredentials } from "@/components/admin/credentials-context";
import { TwinStatusBadge } from "@/components/admin/status-badge";
import { ErrorState } from "@/components/admin/error-state";
import { classifyTwinStatus, relativeTime } from "@/lib/agent-factory/status";
import { useToast } from "@/hooks/use-toast";
import { useState } from "react";
import type { Twin } from "@/lib/agent-factory/types";

export default function AdminHome() {
  const { client } = useCredentials();
  const { data: twins, error, isLoading, refetch } = useFactoryQuery<Twin[]>(
    (c, signal) => c.listTwins({ signal }),
    [],
    { pollMs: 15000 },
  );
  const { toast } = useToast();
  const [pendingId, setPendingId] = useState<string | null>(null);

  const runAction = async (twin: Twin, action: "serve" | "stop") => {
    if (!client) return;
    setPendingId(twin.id);
    try {
      if (action === "serve") await client.serveTwin(twin.id);
      else await client.stopTwin(twin.id);
      toast({ title: `Twin ${action === "serve" ? "started" : "stopped"}`, description: twin.name });
      await refetch();
    } catch (err) {
      toast({
        title: `Failed to ${action} twin`,
        description: (err as Error).message,
        variant: "destructive",
      });
    } finally {
      setPendingId(null);
    }
  };

  const summary = computeSummary(twins ?? []);

  return (
    <>
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Twin overview</h1>
          <p className="text-sm text-muted-foreground font-mono mt-1">
            Real-time view of every installed digital twin in this factory.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isLoading} data-testid="overview-refresh">
          <RefreshCcw className={`h-3.5 w-3.5 mr-1 ${isLoading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3" aria-label="summary">
        <SummaryStat label="Installed" value={summary.total} />
        <SummaryStat label="Running" value={summary.running} tone="ok" />
        <SummaryStat label="Idle" value={summary.idle} tone="muted" />
        <SummaryStat label="Errors" value={summary.errors} tone={summary.errors > 0 ? "danger" : "muted"} />
      </section>

      {error ? <ErrorState error={error} onRetry={refetch} context="Loading twins" /> : null}

      {!error && isLoading && !twins && <CardSkeletonGrid />}

      {!error && twins && twins.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center flex flex-col items-center gap-3">
            <Cpu className="h-10 w-10 text-muted-foreground" />
            <div>
              <p className="font-semibold">No twins yet</p>
              <p className="text-sm text-muted-foreground font-mono">
                Import your first twin from a git repo on the Twin Manager.
              </p>
            </div>
            <Button asChild>
              <Link href="/admin/twins" data-testid="empty-go-twins">
                Go to Twin Manager
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {!error && twins && twins.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {twins.map((twin) => {
            const status = classifyTwinStatus(twin);
            return (
              <Card key={twin.id} data-testid={`twin-card-${twin.id}`} className="flex flex-col">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <CardTitle className="text-base font-mono truncate">{twin.name}</CardTitle>
                      <CardDescription className="font-mono text-xs truncate" title={twin.id}>
                        {twin.id}
                      </CardDescription>
                    </div>
                    <TwinStatusBadge status={status} />
                  </div>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col gap-3">
                  {twin.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2">{twin.description}</p>
                  )}
                  <dl className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <Row label="Model" value={twin.model || "—"} />
                    <Row label="Active" value={twin.active ? "yes" : "no"} />
                    <Row label="Activity" value={relativeTime(twin.last_activity_at)} />
                    <Row label="Version" value={twin.version || "—"} />
                  </dl>
                  <div className="flex flex-wrap gap-2 mt-auto pt-2">
                    {twin.active ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void runAction(twin, "stop")}
                        disabled={pendingId === twin.id}
                        data-testid={`twin-stop-${twin.id}`}
                      >
                        <Square className="h-3.5 w-3.5 mr-1" /> Stop
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => void runAction(twin, "serve")}
                        disabled={pendingId === twin.id}
                        data-testid={`twin-serve-${twin.id}`}
                      >
                        <Play className="h-3.5 w-3.5 mr-1" /> Serve
                      </Button>
                    )}
                    <Button asChild variant="outline" size="sm">
                      <Link href={`/admin/threads?twin=${encodeURIComponent(twin.id)}`} data-testid={`twin-inspect-${twin.id}`}>
                        <Eye className="h-3.5 w-3.5 mr-1" /> Inspect
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}

function SummaryStat({ label, value, tone }: { label: string; value: number; tone?: "ok" | "muted" | "danger" }) {
  const toneCls =
    tone === "ok"
      ? "text-emerald-700"
      : tone === "danger"
        ? "text-rose-700"
        : "text-foreground";
  return (
    <Card>
      <CardContent className="p-4 flex items-center gap-3">
        <Activity className={`h-5 w-5 ${toneCls}`} aria-hidden />
        <div>
          <div className={`text-2xl font-mono font-semibold ${toneCls}`} data-testid={`stat-${label.toLowerCase()}`}>
            {value}
          </div>
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-mono">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-muted-foreground uppercase tracking-wider text-[10px]">{label}</dt>
      <dd className="truncate" title={value}>
        {value}
      </dd>
    </div>
  );
}

function CardSkeletonGrid() {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-6 flex flex-col gap-3">
            <Skeleton className="h-5 w-1/2" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-20 w-full" />
            <div className="flex gap-2">
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-8 w-20" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function computeSummary(twins: Twin[]) {
  let running = 0,
    idle = 0,
    errors = 0;
  for (const twin of twins) {
    const status = classifyTwinStatus(twin);
    if (status === "running") running += 1;
    else if (status === "idle") idle += 1;
    else if (status === "error") errors += 1;
  }
  return { total: twins.length, running, idle, errors };
}
