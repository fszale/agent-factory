import { Switch, Route, Redirect } from "wouter";
import { AdminLayout } from "@/components/admin/admin-layout";
import { CredentialsProvider, useCredentials } from "@/components/admin/credentials-context";
import AdminHome from "@/pages/admin/home";
import AdminTwinManager from "@/pages/admin/twins";
import AdminThreads from "@/pages/admin/threads";
import AdminApprovals from "@/pages/admin/approvals";
import AdminAudit from "@/pages/admin/audit";
import AdminSettings from "@/pages/admin/settings";
import AdminOnboarding from "@/pages/admin/onboarding";

export default function AdminApp() {
  return (
    <CredentialsProvider>
      <AdminGate />
    </CredentialsProvider>
  );
}

function AdminGate() {
  const { credentials, isReady } = useCredentials();

  if (!isReady) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center bg-background text-foreground">
        <div className="text-sm font-mono text-muted-foreground">Loading…</div>
      </div>
    );
  }

  return (
    <Switch>
      <Route path="/admin/onboarding" component={AdminOnboarding} />
      <Route>
        {credentials ? (
          <AdminLayout>
            <Switch>
              <Route path="/admin" component={AdminHome} />
              <Route path="/admin/twins" component={AdminTwinManager} />
              <Route path="/admin/threads" component={AdminThreads} />
              <Route path="/admin/approvals" component={AdminApprovals} />
              <Route path="/admin/audit" component={AdminAudit} />
              <Route path="/admin/settings" component={AdminSettings} />
              <Route>
                <Redirect to="/admin" />
              </Route>
            </Switch>
          </AdminLayout>
        ) : (
          <Redirect to="/admin/onboarding" />
        )}
      </Route>
    </Switch>
  );
}
