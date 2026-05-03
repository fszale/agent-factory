import { useState } from "react";
import { GitBranch, Power, PowerOff, Plus, RefreshCcw } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useFactoryQuery } from "@/hooks/use-factory-query";
import { useCredentials } from "@/components/admin/credentials-context";
import { ErrorState } from "@/components/admin/error-state";
import { TwinStatusBadge } from "@/components/admin/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { classifyTwinStatus, relativeTime } from "@/lib/agent-factory/status";
import type { Twin } from "@/lib/agent-factory/types";

export default function AdminTwinManager() {
  const { client } = useCredentials();
  const { data: twins, error, isLoading, refetch } = useFactoryQuery<Twin[]>(
    (c, signal) => c.listTwins({ signal }),
    [],
  );
  const { toast } = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  const [sourceUrl, setSourceUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [importBusy, setImportBusy] = useState(false);

  const onImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!client) return;
    if (!sourceUrl.trim()) {
      toast({ title: "Source URL required", variant: "destructive" });
      return;
    }
    setImportBusy(true);
    try {
      await client.importTwin({
        source_url: sourceUrl.trim(),
        branch: branch.trim() || undefined,
        active: true,
      });
      toast({ title: "Twin import started" });
      setSourceUrl("");
      setBranch("");
      await refetch();
    } catch (err) {
      toast({ title: "Import failed", description: (err as Error).message, variant: "destructive" });
    } finally {
      setImportBusy(false);
    }
  };

  const onToggleActive = async (twin: Twin, next: boolean) => {
    if (!client) return;
    setBusy(twin.id);
    try {
      await client.setTwinActive(twin.id, next);
      toast({ title: next ? "Twin activated" : "Twin deactivated", description: twin.name });
      await refetch();
    } catch (err) {
      toast({ title: "Update failed", description: (err as Error).message, variant: "destructive" });
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Twin Manager</h1>
          <p className="text-sm text-muted-foreground font-mono mt-1">
            Import twins from git, then install, activate, or deactivate them.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isLoading} data-testid="twins-refresh">
          <RefreshCcw className={`h-3.5 w-3.5 mr-1 ${isLoading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Plus className="h-4 w-4 text-primary" /> Import a twin
          </CardTitle>
          <CardDescription>
            Provide a git URL pointing at a digital-twin spec repository. The factory will clone, install and register it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onImport} className="grid grid-cols-1 md:grid-cols-[1fr_180px_auto] gap-3 items-end" data-testid="twin-import-form">
            <div className="flex flex-col gap-1">
              <Label htmlFor="source_url" className="font-mono text-xs">
                <GitBranch className="h-3.5 w-3.5 inline mr-1" /> Source URL
              </Label>
              <Input
                id="source_url"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://github.com/fszale/digital-twin-filip"
                autoComplete="off"
                data-testid="twin-import-url"
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="branch" className="font-mono text-xs">Branch (optional)</Label>
              <Input
                id="branch"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder="main"
                autoComplete="off"
                data-testid="twin-import-branch"
              />
            </div>
            <Button type="submit" disabled={importBusy} data-testid="twin-import-submit">
              {importBusy ? "Importing…" : "Import & install"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error ? <ErrorState error={error} onRetry={refetch} context="Loading twins" /> : null}

      {!error && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Installed twins</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Last activity</TableHead>
                  <TableHead className="text-right">Active</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading && !twins && (
                  <>
                    {[0, 1, 2].map((i) => (
                      <TableRow key={i}>
                        <TableCell colSpan={5}>
                          <Skeleton className="h-6 w-full" />
                        </TableCell>
                      </TableRow>
                    ))}
                  </>
                )}
                {twins && twins.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-8 font-mono">
                      No twins installed yet.
                    </TableCell>
                  </TableRow>
                )}
                {twins?.map((twin) => (
                  <TableRow key={twin.id} data-testid={`twin-row-${twin.id}`}>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-mono text-sm">{twin.name}</span>
                        <span className="font-mono text-[11px] text-muted-foreground">{twin.id}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <TwinStatusBadge status={classifyTwinStatus(twin)} />
                    </TableCell>
                    <TableCell className="font-mono text-xs">{twin.model || "—"}</TableCell>
                    <TableCell className="font-mono text-xs">{relativeTime(twin.last_activity_at)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        {twin.active ? <Power className="h-3.5 w-3.5 text-emerald-600" /> : <PowerOff className="h-3.5 w-3.5 text-muted-foreground" />}
                        <Switch
                          checked={twin.active}
                          disabled={busy === twin.id}
                          onCheckedChange={(next) => void onToggleActive(twin, next)}
                          data-testid={`twin-toggle-${twin.id}`}
                          aria-label={`Toggle ${twin.name}`}
                        />
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </>
  );
}
