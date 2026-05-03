import { useMemo, useState } from "react";
import { Link, useSearch } from "wouter";
import { ArrowLeft, MessageSquare, RefreshCcw } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useFactoryQuery } from "@/hooks/use-factory-query";
import { ErrorState } from "@/components/admin/error-state";
import { useCredentials } from "@/components/admin/credentials-context";
import { relativeTime } from "@/lib/agent-factory/status";
import type { Paginated, Thread, ThreadMessage, Twin } from "@/lib/agent-factory/types";

const PAGE_SIZE = 25;

export default function AdminThreads() {
  const search = useSearch();
  const params = useMemo(() => new URLSearchParams(search), [search]);
  const threadIdFromUrl = params.get("thread");
  const twinFromUrl = params.get("twin") ?? "all";

  const [twinFilter, setTwinFilter] = useState<string>(twinFromUrl);
  const [page, setPage] = useState(1);

  const { data: twins } = useFactoryQuery<Twin[]>((c, signal) => c.listTwins({ signal }), []);
  const {
    data: threads,
    error,
    isLoading,
    refetch,
  } = useFactoryQuery<Paginated<Thread>>(
    (c, signal) =>
      c.listThreads(
        {
          twin_id: twinFilter !== "all" ? twinFilter : undefined,
          page,
          page_size: PAGE_SIZE,
        },
        { signal },
      ),
    [twinFilter, page],
  );

  if (threadIdFromUrl) {
    return <ThreadDetail threadId={threadIdFromUrl} />;
  }

  return (
    <>
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Threads</h1>
          <p className="text-sm text-muted-foreground font-mono mt-1">
            Conversations across every twin, with run status and token usage.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={twinFilter}
            onValueChange={(value) => {
              setTwinFilter(value);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-56" data-testid="threads-twin-filter">
              <SelectValue placeholder="Filter by twin" />
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
          <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isLoading} data-testid="threads-refresh">
            <RefreshCcw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </header>

      {error ? <ErrorState error={error} onRetry={refetch} context="Loading threads" /> : null}

      {!error && (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Twin</TableHead>
                  <TableHead>Messages</TableHead>
                  <TableHead>Last run</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Open</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading && !threads && (
                  <>
                    {[0, 1, 2, 3].map((i) => (
                      <TableRow key={i}>
                        <TableCell colSpan={6}>
                          <Skeleton className="h-6 w-full" />
                        </TableCell>
                      </TableRow>
                    ))}
                  </>
                )}
                {threads && threads.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-sm text-muted-foreground font-mono">
                      No threads yet.
                    </TableCell>
                  </TableRow>
                )}
                {threads?.items.map((thread) => (
                  <TableRow key={thread.id} data-testid={`thread-row-${thread.id}`}>
                    <TableCell className="font-medium max-w-[28ch] truncate">{thread.title}</TableCell>
                    <TableCell className="font-mono text-xs">{thread.twin_name ?? thread.twin_id}</TableCell>
                    <TableCell className="font-mono text-xs">{thread.message_count}</TableCell>
                    <TableCell className="font-mono text-xs">{thread.last_run_status ?? "—"}</TableCell>
                    <TableCell className="font-mono text-xs">{relativeTime(thread.updated_at)}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="outline">
                        <Link href={`/admin/threads?thread=${encodeURIComponent(thread.id)}`} data-testid={`thread-open-${thread.id}`}>
                          Open
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {threads && threads.total > PAGE_SIZE && (() => {
        const totalPages = Math.max(1, Math.ceil(threads.total / PAGE_SIZE));
        return (
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-muted-foreground">
              Page {threads.page} of {totalPages} · {threads.total} thread{threads.total === 1 ? "" : "s"}
            </span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} data-testid="threads-prev">
                Prev
              </Button>
              <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} data-testid="threads-next">
                Next
              </Button>
            </div>
          </div>
        );
      })()}
    </>
  );
}

function ThreadDetail({ threadId }: { threadId: string }) {
  const { client } = useCredentials();
  const { data, error, isLoading, refetch } = useFactoryQuery<ThreadMessage[]>(
    (c, signal) => c.getThreadMessages(threadId, { signal }),
    [threadId],
  );

  return (
    <>
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="sm" className="font-mono">
            <Link href="/admin/threads" data-testid="thread-back">
              <ArrowLeft className="h-3.5 w-3.5 mr-1" /> All threads
            </Link>
          </Button>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Thread</h1>
            <p className="text-xs text-muted-foreground font-mono">{threadId}</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={!client || isLoading}>
          <RefreshCcw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
        </Button>
      </header>

      {error ? <ErrorState error={error} onRetry={refetch} context="Loading messages" /> : null}

      {!error && isLoading && !data && (
        <Card>
          <CardContent className="p-6 flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </CardContent>
        </Card>
      )}

      {!error && data && data.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center flex flex-col items-center gap-3">
            <MessageSquare className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground font-mono">No messages in this thread.</p>
          </CardContent>
        </Card>
      )}

      {!error && data && data.length > 0 && (
        <div className="flex flex-col gap-3">
          {data.map((msg) => (
            <Card key={msg.id} data-testid={`message-${msg.id}`}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <CardTitle className="text-sm font-mono uppercase tracking-wider">
                    {msg.role}
                  </CardTitle>
                  <CardDescription className="font-mono text-[11px] flex flex-wrap gap-x-3 gap-y-1">
                    <span>{relativeTime(msg.created_at)}</span>
                    {msg.model && <span>model: {msg.model}</span>}
                    {msg.status && <span>status: {msg.status}</span>}
                    {typeof msg.total_tokens === "number" && (
                      <span>
                        tokens: {msg.total_tokens}
                        {typeof msg.prompt_tokens === "number" && (
                          <> ({msg.prompt_tokens} in / {msg.completion_tokens ?? 0} out)</>
                        )}
                      </span>
                    )}
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="text-sm font-mono whitespace-pre-wrap break-words">{msg.content}</pre>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
