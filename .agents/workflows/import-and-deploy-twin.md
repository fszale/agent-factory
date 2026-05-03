# Workflow: import and deploy a twin

Goal: take a digital-twin spec from a git URL to a serving, governed twin in
the factory.

Prereqs:

- The factory backend is running and reachable.
- You have an API key with twin-management scope.
- You're authenticated in the dashboard (`/admin/onboarding` or Settings).

## Steps

1. **Confirm the spec is ready**
   - Open the source repo. Verify it has a top-level twin spec
     (`agent.yaml` / `twin.yaml`) and a `README` describing the model and
     tools.
   - If anything is missing, fix the spec before importing.

2. **Import via the dashboard**
   - Go to `/admin/twins` → "Import a twin".
   - Paste the source URL; optionally set a branch.
   - Click "Import & install".
   - The dashboard will show the twin with status `Installing`.

3. **Watch installation**
   - Refresh the table or wait for the next 15s poll on the overview.
   - On success the status flips to `Idle` (or `Running` once activity arrives).
   - On failure the status is `Error`. Open the audit log
     (`/admin/audit?action=twin.install&twin=<id>`) to read the stderr.

4. **Activate**
   - The Twin Manager toggle controls `active`. Imported twins start active by
     default; deactivate to pause without uninstalling.

5. **Serve**
   - From the overview, click "Serve" if the status is Stopped. The dashboard
     fires `POST /twins/{id}/serve` and updates the card on the next poll.

6. **Sanity-check via threads**
   - Open `/admin/threads?twin=<id>`.
   - If the twin has been used, the threads list will populate. Open one to
     see message history, model used, and token counts.

7. **Audit the install**
   - Open `/admin/audit?twin=<id>`.
   - You should see at least: `twin.install`, `twin.activate`, `twin.serve`.

## Rollback

If the twin behaves badly:

1. Toggle `active` off in Twin Manager (preserves state).
2. Or `POST /twins/{id}/stop` then uninstall via the backend CLI if needed.
3. Audit log captures every step, so the rollback itself is auditable.

## When to escalate

- Install fails with stderr you don't recognize → file an issue with the
  audit row's `metadata.stderr` attached.
- The twin runs but no threads ever appear → the model provider key may be
  missing or scoped wrong; check the factory's environment.
