import { useMemo, useState } from "react";
import { RefreshCcw, ScrollText, Search } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { useFactoryQuery } from "@/hooks/use-factory-query";
import { ErrorState } from "@/components/admin/error-state";
import { applyAuditFilter, paginate, uniqueValues } from "@/lib/agent-factory/filters";
import { relativeTime } from "@/lib/agent-factory/status";
import type { AuditEntry, Paginated, Twin } from "@/lib/agent-factory/types";

const PAGE_SIZE = 25;
const FETCH_SIZE = 500;
const FETCH_CAP_NOTICE = `Filtering against the most recent ${FETCH_SIZE} entries. For deeper history, narrow the date range or query the backend directly.`;

export default function AdminAudit() {
  const [twinFilter, setTwinFilter] = useState<string>("all");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);

  const { data: twins } = useFactoryQuery<Twin[]>((c, signal) => c.listTwins({ signal }), []);
  const {
    data: auditPage,
    error,
    isLoading,
    refetch,
  } = useFactoryQuery<Paginated<AuditEntry>>(
    (c, signal) => c.listAudit({ page: 1, page_size: FETCH_SIZE }, { signal }),
    [],
  );

  const allEntries = auditPage?.items ?? [];
  const filtered = useMemo(
    () =>
      applyAuditFilter(allEntries, {
        twinId: twinFilter,
        action: actionFilter,
        search,
        startDate: startDate || null,
        endDate: endDate || null,
      }),
    [allEntries, twinFilter, actionFilter, search, startDate, endDate],
  );
  const paged = useMemo(
    () => paginate(filtered, { page, pageSize: PAGE_SIZE }),
    [filtered, page],
  );
  const actions = useMemo(() => uniqueValues(allEntries, "action"), [allEntries]);

  const reset = () => {
    setTwinFilter("all");
    setActionFilter("all");
    setSearch("");
    setStartDate("");
    setEndDate("");
    setPage(1);
  };

  return (
    <>
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Audit log</h1>
          <p className="text-sm text-muted-foreground font-mono mt-1">
            Every action taken in this factory, filterable by twin, action and date range.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isLoading} data-testid="audit-refresh">
          <RefreshCcw className={`h-3.5 w-3.5 mr-1 ${isLoading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </header>

      <Card>
        <CardContent className="p-4 grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <div className="flex flex-col gap-1 md:col-span-2">
            <Label className="font-mono text-xs">
              <Search className="h-3.5 w-3.5 inline mr-1" /> Search
            </Label>
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="action, actor, target, metadata…"
              data-testid="audit-search"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="font-mono text-xs">Twin</Label>
            <Select
              value={twinFilter}
              onValueChange={(v) => {
                setTwinFilter(v);
                setPage(1);
              }}
            >
              <SelectTrigger data-testid="audit-twin-filter">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All twins</SelectItem>
                {twins?.map((twin) => (
                  <SelectItem key={twin.id} value={twin.id}>
                    {twin.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label className="font-mono text-xs">Action</Label>
            <Select
              value={actionFilter}
              onValueChange={(v) => {
                setActionFilter(v);
                setPage(1);
              }}
            >
              <SelectTrigger data-testid="audit-action-filter">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All actions</SelectItem>
                {actions.map((a) => (
                  <SelectItem key={a} value={a}>
                    {a}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label className="font-mono text-xs">From</Label>
            <Input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              data-testid="audit-start"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="font-mono text-xs">To</Label>
            <Input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(1);
              }}
              data-testid="audit-end"
            />
          </div>
          <div className="md:col-span-5 flex justify-end">
            <Button variant="ghost" size="sm" onClick={reset} data-testid="audit-reset">
              Reset filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {error ? <ErrorState error={error} onRetry={refetch} context="Loading audit log" /> : null}

      {!error && allEntries.length >= FETCH_SIZE ? (
        <div
          className="rounded-md border border-amber-300/60 bg-amber-50 text-amber-900 px-3 py-2 text-xs font-mono"
          data-testid="audit-cap-notice"
        >
          {FETCH_CAP_NOTICE}
        </div>
      ) : null}

      {!error && (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Twin</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading && allEntries.length === 0 && (
                  <>
                    {[0, 1, 2].map((i) => (
                      <TableRow key={i}>
                        <TableCell colSpan={6}>
                          <Skeleton className="h-6 w-full" />
                        </TableCell>
                      </TableRow>
                    ))}
                  </>
                )}
                {!isLoading && paged.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6}>
                      <div className="flex flex-col items-center gap-2 py-8 text-sm text-muted-foreground font-mono">
                        <ScrollText className="h-8 w-8" />
                        No audit entries match these filters.
                      </div>
                    </TableCell>
                  </TableRow>
                )}
                {paged.items.map((entry) => (
                  <TableRow key={entry.id} data-testid={`audit-row-${entry.id}`}>
                    <TableCell className="font-mono text-xs whitespace-nowrap">
                      {relativeTime(entry.created_at)}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{entry.action}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {entry.twin_name ?? entry.twin_id ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{entry.actor}</TableCell>
                    <TableCell className="font-mono text-xs max-w-[20ch] truncate" title={entry.target ?? ""}>
                      {entry.target ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs max-w-[28ch] truncate" title={JSON.stringify(entry.metadata)}>
                      {entry.metadata ? JSON.stringify(entry.metadata) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {paged.totalPages > 1 && (
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-muted-foreground">
            Page {paged.page} of {paged.totalPages} · {paged.totalItems} entries
          </span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={!paged.hasPrev} onClick={() => setPage((p) => p - 1)} data-testid="audit-prev">
              Prev
            </Button>
            <Button size="sm" variant="outline" disabled={!paged.hasNext} onClick={() => setPage((p) => p + 1)} data-testid="audit-next">
              Next
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
