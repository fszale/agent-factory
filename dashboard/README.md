# dashboard/

A React + Vite admin dashboard for the `agent-factory` backend. Built and
served from Filip's Replit project; mirrored here for backup and reference.

> **Live deployment:** the dashboard ships inside the Replit
> `digital-twin-portal` artifact at the path `/admin`. Open whatever URL the
> portal is published at and append `/admin` (e.g. for the dev preview, the
> base URL printed by `replit dev`; for production, the deploy URL printed
> by `replit deploy`). Both reach the same dashboard.

## What it does

- Real-time twin overview with status cards, model, last activity, and
  serve/stop controls.
- Twin Manager: import twins from a git URL, toggle them active/inactive.
- Threads: paginated thread list with message history, run status, model
  in use, and token counts per message.
- HITL Approval Queue: accept/reject with optional notes; optimistic UI
  with rollback on API failure.
- Audit log: free-text search + twin / action / date filters + paginated
  table.
- Settings: machine API key + base URL, stored in `localStorage` with a
  visible warning banner everywhere.

## How it talks to the backend

A typed fetch client (`src/lib/agent-factory/client.ts`) wraps every REST
endpoint. The API key is sent as both `X-API-Key` and
`Authorization: Bearer <key>`. Errors throw a `FactoryApiError` with a
stable `code` (`unauthorized`, `not_found`, `server_error`, `network_error`
…) the UI can branch on (e.g. show a "Fix credentials" link on 401).

## Structure

```
src/
├── components/admin/           ← layout, status badge, error state, credentials provider
├── hooks/use-factory-query.ts  ← tiny query helper with polling & abort
├── lib/agent-factory/          ← types, auth, client, status, approvals, filters
├── lib/__tests__/              ← agent-factory-* unit tests (61 tests)
└── pages/admin/                ← onboarding, home, twins, threads, approvals, audit, settings
```

## Tests

Pure-logic modules under `src/lib/agent-factory/` are 100% unit-tested:

- `agent-factory-client.test.ts` — typed client + 401/404/500/network errors
- `agent-factory-approvals.test.ts` — pending → approved/rejected
- `agent-factory-filters.test.ts` — filter logic + pagination boundaries
- `agent-factory-status.test.ts` — twin status classification
- `agent-factory-auth.test.ts` — credential storage round-trip

Run from the dashboard's host project:

```bash
pnpm --filter @workspace/digital-twin-portal run test
```

## Why this lives in `digital-twin-portal`

Replit projects cap at 7 artifacts. Rather than create an 8th, the dashboard
ships as a section of the existing `digital-twin-portal` artifact under
`/admin/*`. Same brand, same deploy. The full source under `src/` is what
you see in this mirror's `dashboard/` directory.
