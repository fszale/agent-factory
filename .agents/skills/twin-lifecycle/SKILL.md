---
name: twin-lifecycle
description: Install, serve, toggle, and uninstall digital twins.
---

# Twin Lifecycle

The factory turns a git URL into a serving twin in four steps:
**import → install → register → serve**. This skill explains each step,
where it lives in code, and what to verify before/after a change.

## Mental model

```
+--------+   import   +-----------+  install  +-----------+  serve  +---------+
| git URL| ─────────▶ | cloned    | ────────▶ | installed | ──────▶ | serving |
+--------+            | spec repo |           | twin row  |         | active  |
                      +-----------+           +-----------+         +---------+
                                                  │
                                                  │  toggle inactive
                                                  ▼
                                              +---------+
                                              | stopped |
                                              +---------+
```

Every transition writes an `audit_log` row. The dashboard's
`classifyTwinStatus` derives a presentational status from `(status, active,
last_activity_at)` — keep that helper in sync if you change semantics.

## Where the code lives

- **Backend**
  - `agent_factory/api/twins.py` — REST endpoints (`/twins`, `/twins/import`,
    `/twins/{id}/active`, `/twins/{id}/serve`, `/twins/{id}/stop`).
  - `agent_factory/twins/lifecycle.py` — pure logic for the install pipeline.
  - `agent_factory/db/models/twin.py` — schema.
- **Dashboard mirror**
  - `dashboard/src/pages/admin/twins.tsx` — Twin Manager UI.
  - `dashboard/src/pages/admin/home.tsx` — overview cards + serve/stop.
  - `dashboard/src/lib/agent-factory/status.ts` — `classifyTwinStatus` helper.

## Steps in detail

1. **Import** — `POST /twins/import` with `{ source_url, branch?, active? }`.
   Validates the URL, clones to a sandbox, parses the twin spec.
   - Audit: `twin.install` (or `twin.install` failure with stderr in metadata).
2. **Install** — same call: install dependencies, run health check, write the
   `twins` row in `installing` → `idle`.
3. **Register** — automatic at the end of install; the row is now visible to
   `GET /twins`.
4. **Serve** — `POST /twins/{id}/serve` flips `active=true` and may warm up
   model connections. `POST /twins/{id}/stop` is the inverse.
5. **Toggle active** — `PATCH /twins/{id}/active { active }` for soft pause
   without unloading state.

## Status semantics

| API status | Active flag | Operator sees |
| --- | --- | --- |
| `running` | true | Running |
| `idle` | true, recent activity (<60m) | Running |
| `idle` | true, stale | Idle |
| `error` | any | Error |
| `installing` | true | Installing |
| `stopped` | any | Stopped |
| any | false | Stopped |
| `unknown` | true, recent | Running |
| `unknown` | true, no/old activity | Unknown / Idle |

This table is enforced by `classifyTwinStatus` in
`dashboard/src/lib/agent-factory/status.ts` and tested in
`dashboard/src/lib/__tests__/agent-factory-status.test.ts`.

## Verification before merging a lifecycle change

- [ ] `POST /twins/import` with an invalid URL returns 422 (not 500).
- [ ] An install failure leaves the twin in `error` and writes one audit row.
- [ ] `PATCH /twins/{id}/active` is idempotent.
- [ ] `serve` and `stop` are idempotent.
- [ ] `classifyTwinStatus` and its tests still pass: `pnpm run test` from
      the dashboard host project.
- [ ] An `inactive` twin always renders as `Stopped` in the UI.

## Red flags

- Silent failure paths — every failure must write an audit row.
- New status values added in the API without updating
  `classifyTwinStatus` and the table above.
- `DELETE /twins/{id}` exists but does not also write an audit row.
