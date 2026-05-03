import { useEffect, useState } from "react";
import { useLocation } from "wouter";
import { AlertTriangle, KeyRound, Save, Trash2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCredentials } from "@/components/admin/credentials-context";
import { useToast } from "@/hooks/use-toast";
import { isValidBaseUrl } from "@/lib/agent-factory/auth";

export default function AdminSettings() {
  const { credentials, setCredentials, clearCredentials } = useCredentials();
  const [, navigate] = useLocation();
  const { toast } = useToast();

  const [baseUrl, setBaseUrl] = useState(credentials?.baseUrl ?? "");
  const [apiKey, setApiKey] = useState(credentials?.apiKey ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setBaseUrl(credentials?.baseUrl ?? "");
    setApiKey(credentials?.apiKey ?? "");
  }, [credentials]);

  const onSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidBaseUrl(baseUrl)) {
      setError("Base URL must be a valid http(s) URL.");
      return;
    }
    if (!apiKey.trim()) {
      setError("API key is required.");
      return;
    }
    setError(null);
    setCredentials({ baseUrl, apiKey: apiKey.trim() });
    toast({ title: "Credentials saved" });
  };

  const onClear = () => {
    clearCredentials();
    toast({ title: "Credentials cleared" });
    navigate("/admin/onboarding");
  };

  return (
    <>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground font-mono mt-1">
          Connection details for the agent-factory backend this dashboard talks to.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Connection</CardTitle>
          <CardDescription>
            Stored in <code className="font-mono">localStorage</code>. Switch tools and machines by re-entering the values.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSave} className="flex flex-col gap-4 max-w-xl" data-testid="settings-form">
            <div className="flex flex-col gap-1">
              <Label htmlFor="set-baseurl" className="font-mono text-xs">Base URL</Label>
              <Input
                id="set-baseurl"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://factory.example.com"
                spellCheck={false}
                autoComplete="off"
                data-testid="settings-baseurl"
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="set-apikey" className="font-mono text-xs">
                <KeyRound className="h-3.5 w-3.5 inline mr-1" /> API key
              </Label>
              <Input
                id="set-apikey"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                type="password"
                spellCheck={false}
                autoComplete="off"
                data-testid="settings-apikey"
              />
            </div>

            <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 text-amber-900 p-3 text-xs font-mono">
              <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <p>
                Anyone with access to this browser profile can read your key. Use a scoped, rotatable
                machine key — never the root admin token.
              </p>
            </div>

            {error && (
              <p className="text-sm text-destructive font-mono" role="alert" data-testid="settings-error">
                {error}
              </p>
            )}

            <div className="flex gap-2 justify-end">
              <Button type="button" variant="outline" onClick={onClear} data-testid="settings-clear">
                <Trash2 className="h-3.5 w-3.5 mr-1" /> Clear
              </Button>
              <Button type="submit" data-testid="settings-save">
                <Save className="h-3.5 w-3.5 mr-1" /> Save
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </>
  );
}
