---
name: audit-review
description: Read and reason about the append-only audit log.
---

# Audit Review

`audit_log` is the factory's source of truth for "what happened". This skill
covers how to read it, filter it, and what is forbidden.

## Mental model

Every state-changing event in the factory writes one row:

```
{
  id: uuid,
  created_at: timestamptz,
  twin_id: uuid | null,
  twin_name: text | null,    -- denormalized for the dashboard
  action: text,              -- e.g. "twin.install", "approval.accept"
  actor: text,               -- "filip" or "system" or a key owner label
  target: text | null,       -- the affected resource id, when applicable
  metadata: jsonb | null     -- structured context (stderr, notes, etc)
}
```

Rows are append-only. No `UPDATE`, no `DELETE`, ever. Backfills are new
rows with `metadata.references = "<original-id>"`.

## Common actions you'll see

| Action | When it fires |
| --- | --- |
| `twin.install` | After a successful or failed `POST /twins/import` |
| `twin.uninstall` | After a successful uninstall |
| `twin.activate` / `twin.deactivate` | On `PATCH /active` |
| `twin.serve` / `twin.stop` | On serve/stop endpoints |
| `thread.create` | First message creates a thread |
| `run.start` / `run.complete` / `run.fail` | Orchestrator transitions |
| `approval.request` | An HITL row is created |
| `approval.accept` / `approval.reject` | Operator decides |
| `config.change` | Factory or twin config edited |

If you add a new action, register it here.

## Where the code lives

- **Backend**
  - `agent_factory/api/audit.py` — `GET /audit?twin_id=&action=&start=&end=&page=&page_size=`.
  - `agent_factory/db/models/audit.py` — schema.
  - `agent_factory/services/audit.py` — the only legal write path.
- **Dashboard mirror**
  - `dashboard/src/pages/admin/audit.tsx` — filter + paginated table.
  - `dashboard/src/lib/agent-factory/filters.ts` — pure filter & pagination
    logic, fully unit-tested in
    `dashboard/src/lib/__tests__/agent-factory-filters.test.ts`.

## Filter semantics

The dashboard fetches up to `FETCH_SIZE = 500` rows and filters in the
client. This is fast and lets the operator combine free-text search with
twin / action / date filters. AND semantics across all filters; the
date range is **inclusive on both ends** (`endDate` snaps to 23:59:59.999).

If the audit log grows large enough that 500 rows aren't enough, push the
filters server-side and update the dashboard's `useFactoryQuery` call.

## Verification before merging an audit change

- [ ] No new code path writes to `audit_log` outside `services/audit.py`.
- [ ] No `UPDATE` or `DELETE` SQL targets `audit_log`.
- [ ] Filter helpers + pagination tests still pass.
- [ ] Pagination boundary tests (page 0, page 99, empty list) all behave.
- [ ] Free-text search continues to be case-insensitive and to search across
      action, actor, target, twin name, and metadata.

## Red flags

- A migration that drops or rewrites historical rows.
- A new action introduced in the backend that the dashboard never displays.
- Adding mutable columns to `audit_log` (e.g., `notes` editable after
  creation). Notes go into a fresh row referencing the original.
