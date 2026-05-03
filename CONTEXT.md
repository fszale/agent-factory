# CONTEXT.md — deeper architecture & invariants

This file expands [`README.md`](./README.md) for engineers and AI agents who
need the full mental model. It is the canonical place to add architectural
notes, decisions, and trade-offs.

---

## Domain language

| Term | Meaning |
| --- | --- |
| **Twin** | A digital-twin spec installed in this factory. Has an id, model, status (`running` / `idle` / `error` / `installing` / `stopped`), and an `active` flag. |
| **Run** | One execution of a twin against a thread. Carries status (`queued` → `running` → `completed` / `failed` / `cancelled` / `awaiting_approval`) and token counters. |
| **Thread** | A conversation against one twin. Lists messages chronologically. |
| **Approval** | An HITL checkpoint blocking a tool call until a human accepts or rejects it. |
| **Audit entry** | An append-only record of an action taken in the factory. |
| **Operator** | The human using the admin dashboard. |

---

## Invariants

Two invariants are non-negotiable:

### 1. HITL gates risky actions

Tool calls flagged as risky in a twin spec **must** create an approval row
in `pending` status and **must not** execute until the row transitions to
`approved`. This is enforced at the run-orchestration layer, not the
individual tool. Tests guard the transition table:

```
pending → approved
pending → rejected
approved → (terminal)
rejected → (terminal)
```

The dashboard's `applyDecision` helper enforces the same transitions
client-side; if you change the table, change both sides plus the unit tests
in `dashboard/src/lib/__tests__/agent-factory-approvals.test.ts`.

### 2. Audit log is append-only

The audit table never sees `UPDATE` or `DELETE`. Backfills happen via new
rows that reference the original. Write helpers should refuse to mutate
existing rows. Reviewers should reject any PR that introduces an UPDATE.

---

## Lifecycle pipeline

```
git URL  ──▶  clone  ──▶  install  ──▶  register  ──▶  serve
                                                ▲
                                                │  toggle active/inactive
                                                ▼
                                              stop
```

Each transition writes an audit row (`twin.install`, `twin.activate`, …).
A failed install leaves the twin in `error` status with the failure recorded
in audit metadata.

---

## Run orchestration

For each user message in a thread:

1. Create a `run` row in `queued` status.
2. Move to `running` and stream model output back to the thread.
3. If a tool call is risky, create an `approval` row and transition the run
   to `awaiting_approval`. The run resumes when the approval is decided.
4. On final response, move to `completed` (or `failed` on exception). Record
   token counters on the assistant message row.

The dashboard's Threads view reads token counts straight from those rows.

---

## Auth model

The factory uses **machine API keys**. There is no user model in the backend
itself — the operator's identity comes from the key's owner. Keys are
provisioned out-of-band (Supabase row + secret) and rotated on suspicion.

The dashboard sends the key as both `X-API-Key` and `Authorization: Bearer`.
Backends that prefer one over the other can ignore the other.

When the key is invalid, the API returns `401`, the dashboard's
`FactoryApiError.code` is `"unauthorized"`, and the operator is offered a
"Fix credentials" link to the Settings page.

---

## Storage layout (Supabase)

| Table | Purpose |
| --- | --- |
| `twins` | One row per installed twin. |
| `threads` | One row per conversation. |
| `messages` | Append-only message history. |
| `runs` | One row per twin execution; FK to `threads` and `messages`. |
| `approvals` | HITL queue. State transitions enforced via RLS + app code. |
| `audit_log` | Append-only event log. |
| `api_keys` | Hashed key material + scope metadata. |

Indexes: `(twin_id, created_at desc)` on `messages`, `runs`, `audit_log`,
`approvals`. The dashboard's audit filter assumes server-side ordering by
`created_at desc`.

---

## Failure modes worth knowing

- **Installation fails** → twin stays `error`, install audit row carries the
  stderr. The dashboard's `classifyTwinStatus` keeps inactive twins as
  `stopped` regardless of the underlying status.
- **Approval timeout** → not auto-approved. Operator must decide. (We may
  add expiry rows in the future; do not add silent auto-approval.)
- **Run crashes mid-execution** → status moves to `failed`, audit row
  records `run.fail` with the exception message. Tokens are still accounted
  for on whatever messages persisted.

---

## Roadmap notes

- Streaming SSE for thread messages — currently the dashboard polls every
  15s on the overview, 20s on the approval queue. Replace with SSE when the
  backend ships streaming.
- Per-twin scoped API keys — today a single factory key sees all twins. The
  scoping fields exist in the schema but are not enforced everywhere.
- Mobile dashboard — out of scope. The current React app is desktop-first.

If you add to this list, link to the work item or PR.
