import { useState } from "react";
import { useLocation } from "wouter";
import { motion } from "framer-motion";
import { Hexagon, KeyRound, ServerCog, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCredentials } from "@/components/admin/credentials-context";
import { isValidBaseUrl } from "@/lib/agent-factory/auth";

export default function AdminOnboarding() {
  const { setCredentials } = useCredentials();
  const [, navigate] = useLocation();
  const [baseUrl, setBaseUrl] = useState("http://localhost:8000");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedKey = apiKey.trim();
    if (!isValidBaseUrl(baseUrl)) {
      setError("Base URL must be a valid http(s) URL.");
      return;
    }
    if (!trimmedKey) {
      setError("API key is required.");
      return;
    }
    setError(null);
    setCredentials({ baseUrl, apiKey: trimmedKey });
    navigate("/admin");
  };

  return (
    <div className="min-h-[100dvh] bg-background flex flex-col font-sans">
      <div className="flex-1 flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="w-full max-w-xl"
      >
        <div className="flex items-center gap-2 mb-6">
          <Hexagon className="h-7 w-7 text-primary" />
          <div>
            <h1 className="font-mono font-bold text-lg">agent-factory admin</h1>
            <p className="text-xs text-muted-foreground font-mono">solidcage.com · governed AI employees</p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Connect your Agent Factory</CardTitle>
            <CardDescription>
              Point this dashboard at a running agent-factory backend. Credentials are kept in this
              browser only — they never round-trip through solidcage.com.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="flex flex-col gap-4" data-testid="onboarding-form">
              <div className="flex flex-col gap-2">
                <Label htmlFor="baseUrl" className="font-mono text-xs">
                  <ServerCog className="h-3.5 w-3.5 inline mr-1" /> Base URL
                </Label>
                <Input
                  id="baseUrl"
                  data-testid="onboarding-baseurl"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://factory.example.com"
                  autoComplete="off"
                  spellCheck={false}
                />
                <p className="text-xs text-muted-foreground font-mono">FastAPI host without a trailing slash.</p>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="apiKey" className="font-mono text-xs">
                  <KeyRound className="h-3.5 w-3.5 inline mr-1" /> Machine API key
                </Label>
                <Input
                  id="apiKey"
                  data-testid="onboarding-apikey"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  type="password"
                  placeholder="sk_factory_…"
                  autoComplete="off"
                  spellCheck={false}
                />
                <p className="text-xs text-muted-foreground font-mono">
                  Sent as both <code>X-API-Key</code> and <code>Authorization: Bearer</code>.
                </p>
              </div>

              <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 text-amber-900 p-3 text-xs font-mono">
                <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <p>
                  This key is stored in your browser's <span className="font-semibold">localStorage</span>. Anyone
                  with access to this device can read it. Use a scoped key.
                </p>
              </div>

              {error && (
                <p className="text-sm text-destructive font-mono" role="alert" data-testid="onboarding-error">
                  {error}
                </p>
              )}

              <div className="flex justify-end">
                <Button type="submit" data-testid="onboarding-submit">
                  Connect
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground font-mono mt-4">
          Need a backend?{" "}
          <a href="https://github.com/fszale/agent-factory" target="_blank" rel="noreferrer" className="hover:text-primary">
            github.com/fszale/agent-factory
          </a>
        </p>
      </motion.div>
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
            <a href="https://crm.solidcage.com/widget/bookings/filip-szalewicz-fractional-cto-calendar-vfs0lblxh" target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-primary transition-colors">
              book
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
