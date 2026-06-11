# Phase 0 Audit — agent-factory

> Audited: 2026-05-28. Scope: runtime reality vs. README claims.

---

## Tools / Integrations

| Component | Status | Notes |
|---|---|---|
| **Model provider: xAI (Grok)** | WORKING | `XAIResponsesProvider` — full implementation, calls `api.x.ai/v1/responses`, auth via env `XAI_API_KEY`. |
| **Model provider: Stub** | WORKING | `StubProvider` — returns deterministic echo responses; used in tests and dev. |
| **Model provider: OpenAI / GPT** | MISSING | No `OpenAIProvider` class exists. Plan §3.1 references `gpt-5.5` profile; not yet implemented. |
| **Knowledge retrieval** | WORKING | `InMemoryKnowledgeBase` — TF-IDF-style token overlap scoring; loads `.md` / text files from twin spec dir. No pgvector / semantic search yet. |
| **Twin installer** | WORKING | `install_twin()` — copies source dir, validates `twin.yaml` via Pydantic, raises on collision unless `overwrite=True`. |
| **Twin registry** | WORKING | `TwinRegistry` — scans `installed_twins/` for `*/twin.yaml`, builds `TwinPackage` per twin. |
| **Twin runtime / chat** | WORKING | `TwinRuntime.chat()` — resolves model profile, retrieves context, calls provider, returns `TwinChatResult`. HITL gate not wired into chat path yet (see below). |
| **Kernel sync** | WORKING | `sync_kernel_artifacts()` — copies kernel files/dirs from a local checkout into a twin dir. Requires local path; no git-fetch / pinned-version resolution yet. |
| **Persistence: InMemory** | WORKING | Full `InMemoryStore` — all 11 tables backed by dicts; used in tests and local dev. |
| **Persistence: Supabase** | WORKING | `SupabaseStore` — full REST implementation for all tables. Requires `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`. |
| **Auth / API keys** | WORKING | `AuthService` + `generate_api_key()` — prefix+hash scheme, `X-API-Key` / `Bearer` support. |
| **FastAPI app** | WORKING | All endpoints in README present: twins, threads, messages, runs, tasks, events, approvals, corrections, artifact proposals, audit, admin identities, API clients. |
| **HITL approval queue** | STUBBED | `approvals` table + endpoints exist and are tested. BUT the run orchestrator (`TwinRuntime.chat`) does not yet gate `always_gate` actions through it — HITL is callable via API but not enforced in the hot path. |
| **Budget / usage meter** | MISSING | No token or USD counter is decremented per provider call. `runs` table has fields for token tracking but `TwinRuntime` never writes them. Hard-stop enforcement before provider return (required by plan §10) is absent. |
| **Kill switch** | MISSING | No per-twin or factory-wide pause flag checked at task dispatch. |
| **Model router** | STUBBED | `model_profiles` in `twin.yaml` maps profile names to providers/models; runtime selects by profile key. No capability-based routing logic (e.g., "research → openai, social → xai"). |
| **Task queue (Cloud Tasks / SQS)** | MISSING | `tasks` table exists; no async queue backend. Tasks created/updated via DB only. |
| **Scheduler (Cloud Scheduler / EventBridge)** | MISSING | No scheduler integration. |
| **Peer MCP server** | MISSING | Not started. Plan §3.3 target for Phase 2. |
| **Improvement loop** | MISSING | `corrections` + `artifact_proposals` tables exist. No reflect/score/PR pipeline. Phase 2 target. |
| **Dashboard** | STUBBED | React admin app in `dashboard/` is a mirror/backup. Deployed separately via Replit/Vercel. Not part of factory build yet. |
| **CLI (`factory twin build/deploy`)** | MISSING | `cli.py` exists but build/deploy subcommands for the Phase 1 twin-builder pipeline are not implemented. |
| **Multi-cloud deploy modules** | MISSING | No `deploy/gcp/` or `deploy/aws/` Terraform. Dockerfile exists. |

---

## Persistence Tables (Supabase schema)

All tables defined in `supabase/schema.sql` and mirrored in `InMemoryStore`:

| Table | Exists in schema | Exists in InMemory | Notes |
|---|---|---|---|
| `threads` | ✓ | ✓ | |
| `messages` | ✓ | ✓ | Token counts tracked in `metadata` jsonb, not dedicated columns. |
| `runs` | ✓ | ✓ | `provider` / `model` columns present but never populated by runtime. |
| `tasks` | ✓ | ✓ | No async dispatch backend. |
| `events` | ✓ | ✓ | |
| `approvals` | ✓ | ✓ | Not enforced in hot path. |
| `corrections` | ✓ | ✓ | |
| `artifact_proposals` | ✓ | ✓ | |
| `api_clients` | ✓ | ✓ | |
| `admin_identities` | ✓ | ✓ | |
| `audit_events` | ✓ | ✓ | Append-only enforced by convention; no DB trigger. |

---

## Gap summary (Phase 1 must-closes)

1. **HITL enforcement in hot path** — wire approval gate into `TwinRuntime` before `always_gate` actions execute.
2. **Budget/usage meter** — decrement token + USD counters atomically per provider call; hard-stop before return.
3. **Kill switch** — per-twin + factory-wide pause flag, checked at top of every task dispatch.
4. **OpenAI provider** — needed for `research` profile in the plan's model router.
5. **`twin.yaml` schema upgrade** — add `kernel.source` (required) + full `autonomy` block (see schemas/).
6. **Twin-builder CLI** — `factory twin build <twin.yaml>` → resolves pinned kernel + bridge → artifact.

---

## Rationalization note

Score 9/10: The existing codebase is a solid, well-tested substrate. The gaps are additive (new modules), not rework. Persistence, auth, and the approval data model are all load-bearing and correct. Phase 1 builds on top, not over.
