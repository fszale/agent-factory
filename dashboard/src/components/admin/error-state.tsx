import { AlertTriangle, RefreshCcw, KeyRound } from "lucide-react";
import { Link } from "wouter";
import { Button } from "@/components/ui/button";
import { FactoryApiError } from "@/lib/agent-factory/client";

export function ErrorState({
  error,
  onRetry,
  context,
}: {
  error: unknown;
  onRetry?: () => void;
  context?: string;
}) {
  const isUnauthorized = error instanceof FactoryApiError && error.status === 401;
  const message = error instanceof Error ? error.message : "Something went wrong.";
  const code = error instanceof FactoryApiError ? error.code : "unknown";

  return (
    <div
      className="rounded-xl border border-rose-200 bg-rose-50 text-rose-900 p-6 flex flex-col gap-3"
      data-testid="error-state"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 mt-0.5" aria-hidden />
        <div className="flex-1 min-w-0">
          <p className="font-semibold font-mono text-sm">
            {context ? `${context} failed` : "Request failed"}
            <span className="ml-2 text-xs opacity-70">({code})</span>
          </p>
          <p className="text-sm mt-1 font-mono break-words">{message}</p>
        </div>
      </div>
      <div className="flex gap-2 ml-8">
        {onRetry && (
          <Button size="sm" variant="outline" onClick={onRetry} data-testid="error-retry">
            <RefreshCcw className="h-3.5 w-3.5 mr-1" /> Retry
          </Button>
        )}
        {isUnauthorized && (
          <Button asChild size="sm" variant="outline">
            <Link href="/admin/settings" data-testid="error-fix-credentials">
              <KeyRound className="h-3.5 w-3.5 mr-1" /> Fix credentials
            </Link>
          </Button>
        )}
      </div>
    </div>
  );
}
