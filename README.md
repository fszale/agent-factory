# agent-factory

Governed AI employees, with humans in the loop. A FastAPI + Supabase backend that
imports digital-twin specs from git, installs them as servable agents, runs them
through threaded conversations, and gates risky actions through an HITL approval
queue. Ships with a React admin dashboard so operators can actually drive it.

> **Build your own twin factory — [solidcage.com](https://solidcage.com)**
>
> Filip Szalewicz uses this stack with manufacturing and engineering clients to
> turn role specs into governed AI employees in 2–6 weeks.
> [Book a working session →](https://crm.solidcage.com/widget/bookings/filip-szalewicz-fractional-cto-calendar-vfs0lblxh)

---

## Architecture overview

```
┌──────────────────────┐      ┌────────────────────────────┐
│   Operator (HITL)    │◀────▶│   Admin Dashboard (React)  │
└──────────────────────┘      │   solidcage.com / Replit   │
                              └─────────────┬──────────────┘
                                            │  REST + X-API-Key
                                            ▼
                       ┌────────────────────────────────────┐
                       │      agent-factory  (FastAPI)      │
                       │  ┌──────────────────────────────┐  │
                       │  │ Twin registry / installer    │  │
                       │  │ Threads + run orchestration  │  │
                       │  │ HITL approval queue          │  │
                       │  │ Audit log                    │  │
                       │  └──────────────────────────────┘  │
                       └─────────────┬──────────────────────┘
                                     │
                  ┌──────────────────┼─────────────────────┐
                  ▼                  ▼                     ▼
         ┌──────────────┐  ┌──────────────────┐  ┌─────────────────┐
         │  Supabase    │  │ Twin git sources │  │ Model providers │
         │ (state, log) │  │ (spec repos)     │  │ (LLM API)       │
         └──────────────┘  └──────────────────┘  └─────────────────┘
```

Three responsibilities:

1. **Lifecycle** — clone a twin spec from git, install dependencies, register
   it, and toggle it active. See [`.agents/skills/twin-lifecycle`](./.agents/skills/twin-lifecycle/SKILL.md).
2. **Governance** — every risky tool call surfaces in an approval queue;
   nothing executes without a human decision. See
   [`.agents/skills/hitl-governance`](./.agents/skills/hitl-governance/SKILL.md).
3. **Audit** — append-only log of every twin/run/approval/config event,
   queryable by twin, action, and date. See
   [`.agents/skills/audit-review`](./.agents/skills/audit-review/SKILL.md).

---

## Quick start

### Backend

```bash
git clone https://github.com/fszale/agent-factory
cd agent-factory
cp .env.example .env  # set SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY, FACTORY_API_KEY
uv sync               # or: pip install -r requirements.txt
uv run uvicorn agent_factory.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Health check:

```bash
curl -H "X-API-Key: $FACTORY_API_KEY" http://localhost:8000/healthz
```

### Admin dashboard

Two ways to run the dashboard:

**Live deployment** — the dashboard is mounted at `<DEPLOY_URL>/twin-portal/admin` of the
SolidCage Replit Deployment (replace `<DEPLOY_URL>` with the live `*.replit.app`
host from the Publishing tool, or the configured custom domain such as
`apps.solidcage.com`). Open `<DEPLOY_URL>/twin-portal/admin/onboarding` and paste your
factory base URL + API key.

**Local development** — the dashboard source is mirrored from the Replit
project under [`./dashboard/`](./dashboard/) for backup and reference. To run
it standalone, copy it into a Vite project (or read the linked source for the
full pnpm-monorepo setup).

---

## API surface

| Resource | Method | Path | Notes |
| --- | --- | --- | --- |
| Twins | GET | `/twins` | List all installed twins |
| Twins | GET | `/twins/{id}` | Single twin |
| Twins | POST | `/twins/import` | `{ source_url, branch?, active? }` |
| Twins | PATCH | `/twins/{id}/active` | `{ active: bool }` |
| Twins | POST | `/twins/{id}/serve` | Start serving |
| Twins | POST | `/twins/{id}/stop` | Stop serving |
| Threads | GET | `/threads?twin_id=&page=&page_size=` | Paginated |
| Threads | GET | `/threads/{id}/messages` | Full message history |
| Approvals | GET | `/approvals?status=&page=&page_size=` | Paginated |
| Approvals | POST | `/approvals/{id}/accept` | `{ notes? }` |
| Approvals | POST | `/approvals/{id}/reject` | `{ notes? }` |
| Audit | GET | `/audit?twin_id=&action=&start=&end=&page=&page_size=` | Paginated |
| Health | GET | `/healthz` | No auth |

All non-health endpoints require an API key in either the
`X-API-Key` header or `Authorization: Bearer <key>`. Requests reject `401` when
the key is missing or unrecognized.

Errors follow FastAPI conventions:

```json
{ "detail": "Twin 'xyz' not found" }
```

The dashboard's typed client (`dashboard/src/lib/agent-factory/client.ts`)
parses these into a `FactoryApiError` with a stable `code` string
(`unauthorized`, `not_found`, `server_error`, `network_error`, …).

---

## Repo layout

```
.
├── README.md                  ← you are here
├── AGENTS.md                  ← OpenAI / generic agent guidance
├── CLAUDE.md                  ← Anthropic-specific guidance
├── CONTEXT.md                 ← deeper architecture & invariants
├── .agents/
│   ├── skills/
│   │   ├── twin-lifecycle/
│   │   ├── hitl-governance/
│   │   └── audit-review/
│   └── workflows/
│       ├── import-and-deploy-twin.md
│       └── review-approvals.md
├── dashboard/                 ← mirror of the React admin app
└── agent_factory/             ← FastAPI app (this repo's primary code)
```

---

## Related work

- [`fszale/agent-kernel`](https://github.com/fszale/agent-kernel) — minimal
  agent runtime used inside twins.
- [`fszale/digital-twin-filip`](https://github.com/fszale/digital-twin-filip) —
  reference twin spec.
- [`fszale/agentic-playbook`](https://github.com/fszale/agentic-playbook) —
  rollout playbook for organizations.
- [`solidcage.com`](https://solidcage.com) — consulting front door.

---

## License

MIT.
