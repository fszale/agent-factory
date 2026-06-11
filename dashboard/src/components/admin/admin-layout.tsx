import { Link, useLocation } from "wouter";
import { Hexagon, LayoutDashboard, Users, MessageSquare, ShieldCheck, ScrollText, Settings, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCredentials } from "@/components/admin/credentials-context";
import { cn } from "@/lib/utils";

const ADMIN_NAV = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/admin/twins", label: "Twin Manager", icon: Users },
  { href: "/admin/threads", label: "Threads", icon: MessageSquare },
  { href: "/admin/approvals", label: "Approvals", icon: ShieldCheck },
  { href: "/admin/audit", label: "Audit Log", icon: ScrollText },
  { href: "/admin/settings", label: "Settings", icon: Settings },
];

export function AdminLayout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();
  const { credentials } = useCredentials();

  const isActive = (href: string, exact?: boolean) => {
    if (exact) return location === href;
    return location === href || location.startsWith(`${href}/`);
  };

  return (
    <div className="min-h-[100dvh] flex flex-col bg-background text-foreground font-sans">
      <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/85 backdrop-blur-md">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between gap-4">
          <Link href="/admin" className="flex items-center gap-2 group" data-testid="admin-link-home">
            <Hexagon className="h-6 w-6 text-primary group-hover:text-primary/80 transition-colors" />
            <div className="flex flex-col leading-tight">
              <span className="font-mono font-bold tracking-tight text-sm">agent-factory</span>
              <span className="font-mono text-[10px] text-muted-foreground">admin dashboard</span>
            </div>
          </Link>
          <div className="hidden md:flex items-center gap-2 text-xs font-mono text-muted-foreground truncate max-w-[40ch]">
            {credentials ? (
              <>
                <span className="rounded px-1.5 py-0.5 bg-secondary text-secondary-foreground">API</span>
                <span className="truncate" title={credentials.baseUrl}>{credentials.baseUrl}</span>
              </>
            ) : (
              <span>not connected</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm" className="font-mono text-xs">
              <Link href="/" data-testid="admin-link-portal">portal</Link>
            </Button>
            <Button asChild variant="default" size="sm" className="font-mono">
              <a href="https://cal.com/filip-szalewicz-wl6x3a/30min" target="_blank" rel="noreferrer">
                Book Session
              </a>
            </Button>
          </div>
        </div>
      </header>

      <CredentialBanner />

      <div className="flex-1 container mx-auto px-4 py-6 flex flex-col md:flex-row gap-6">
        <aside className="md:w-56 flex-shrink-0">
          <nav className="flex md:flex-col gap-1 overflow-x-auto md:overflow-visible md:sticky md:top-20" aria-label="Admin navigation">
            {ADMIN_NAV.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href, item.exact);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  data-testid={`admin-nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors hover-elevate whitespace-nowrap",
                    active
                      ? "bg-primary text-primary-foreground hover-elevate-2"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="flex-1 min-w-0 flex flex-col gap-6">{children}</main>
      </div>

      <footer className="border-t border-border/40 bg-card/30">
        <div className="container mx-auto px-4 py-6 flex flex-col md:flex-row justify-between items-center gap-3 text-sm font-mono">
          <a
            href="https://solidcage.com"
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground hover:text-primary transition-colors"
            data-testid="footer-cta"
          >
            Build your own twin factory — solidcage.com
          </a>
          <div className="flex gap-4">
            <a href="https://github.com/fszale/agent-factory" target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-primary transition-colors">
              source
            </a>
            <a href="https://cal.com/filip-szalewicz-wl6x3a/30min" target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-primary transition-colors">
              book
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function CredentialBanner() {
  const { credentials } = useCredentials();
  if (!credentials) return null;
  return (
    <div className="border-b border-amber-300/60 bg-amber-50 text-amber-900" data-testid="credential-warning">
      <div className="container mx-auto px-4 py-2 flex items-start gap-2 text-xs">
        <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" aria-hidden />
        <p className="font-mono">
          API key stored in <span className="font-semibold">localStorage</span>. Use a scoped key with the smallest privileges that work, and never paste production credentials on a shared machine.
        </p>
      </div>
    </div>
  );
}
