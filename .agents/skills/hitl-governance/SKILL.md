---
name: hitl-governance
description: Gate risky tool calls behind human approval, with auditable decisions.
---

# HITL Governance

`agent-factory` only executes risky tool calls after a human says yes. This
skill explains the model, where it lives in code, and the rules for changing
it.

## Mental model

When a twin run reaches a risky tool call:

1. The orchestrator pauses the run (`run.status = awaiting_approval`).
2. An `approvals` row is inserted with `status = pending` and a structured
   summary the operator can act on.
3. The operator decides via the dashboard's HITL queue.
4. The orchestrator resumes with the decision in scope. The decision is
   logged to `audit_log` (`approval.accept` or `approval.reject`).

Approvals are state machines:

```
pending ──accept──▶ approved (terminal)
   │
   └────reject───▶ rejected (terminal)
```

`approved` and `rejected` never re-transition. Trying to do so is an error.
The pure helper `applyDecision` in
`dashboard/src/lib/agent-factory/approvals.ts` encodes this and is
exhaustively tested.

## Where the code lives

- **Backend**
  - `agent_factory/api/approvals.py` — `/approvals`, `/approvals/{id}/accept`,
    `/approvals/{id}/reject`.
  - `agent_factory/runs/orchestrator.py` — the pause/resume gate.
  - `agent_factory/db/models/approval.py` — schema.
- **Dashboard mirror**
  - `dashboard/src/pages/admin/approvals.tsx` — HITL queue UI.
  - `dashboard/src/lib/agent-factory/approvals.ts` — pure transitions.
  - `dashboard/src/lib/__tests__/agent-factory-approvals.test.ts` — guard
    tests for the transition table.

## Operator UX rules

- Pending items always sort newest-first.
- Decisions are optimistic in the UI: the row updates immediately, then
  rolls back on API failure (`revertOptimisticDecision`).
- Notes are optional but encouraged; they ride along to `decided_by` and
  appear in the audit row.
- A rejected approval must not be re-approvable from the UI.

## Test-mode auto-approver

For local development you can set `FACTORY_AUTO_APPROVE=true`. This wires an
in-process auto-approver that **records the same audit rows** as a human
would. It is forbidden in any environment with `FACTORY_ENV=production` or a
non-localhost Supabase URL — the boot check refuses to start.

If a maintainer asks for "approval bypass", offer this auto-approver and ask
why the production gate isn't acceptable.

## Verification before merging an HITL change

- [ ] Pure-logic tests still pass:
      `pnpm --filter @workspace/digital-twin-portal run test` (or equivalent
      in the dashboard host project).
- [ ] The transition table in `applyDecision` matches the backend's
      enforced table.
- [ ] Every accept / reject path writes exactly one audit row.
- [ ] A rejected approval cannot be re-approved via the API.
- [ ] Optimistic UI rollback works on a forced 500 response.

## Red flags

- A code path that executes a risky tool call without first creating an
  `approvals` row.
- A backend "admin override" that mutates an `approvals` row directly.
- Removing the test-mode `production` guard.
- New approval statuses introduced without updating both transition tables.
