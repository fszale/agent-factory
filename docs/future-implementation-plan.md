# Agent Factory Future Implementation Plan

**Plan Owner:** Principal Operator  
**Date Created:** 2026-03-20  
**Context:** `agent-factory` is operational enough for local text-based validation, but it still needs production hardening, deployment, and later realtime voice/avatar support.

---

## Foundation

**Vision** *(What does success look like at 90 days? One precise sentence):*

> `agent-factory` runs one or more installed digital twins with Supabase-backed persistence and governance in production on Cloud Run, while voice and avatar support are designed and ready for a controlled pilot.

**Objectives** *(3–5 measurable objectives):*

| # | Objective | Measurement | Target |
|---|---|---|---|
| 1 | Prove the local runtime works end to end with Supabase | Local setup checklist completed without code changes | 1 successful local operator test flow |
| 2 | Harden the core text and agent APIs before deployment | Critical-path issues discovered in local testing | 0 unresolved P0/P1 issues |
| 3 | Deploy a stable Cloud Run baseline | Successful authenticated deployment with persistent storage | 1 production-like environment running |
| 4 | Establish governance for iterative improvement | Corrections, approvals, and audit workflows exercised | 1 full review-to-promotion dry run |
| 5 | Prepare voice/avatar expansion without destabilizing core text workflows | Approved architecture and pilot backlog | 1 implementation-ready design |

**Key Stakeholders:**

| Stakeholder | Role | Must Be Aligned By | How |
|---|---|---|---|
| Principal Operator | Product owner, governor, source-of-truth identity | Immediately | Review local runtime behavior and approve promotion rules |
| Agent Factory runtime | Control plane for twins, governance, and APIs | Immediately | Validate thread, task, auth, and admin flows locally |
| Supabase | Persistence, auth, and governance backing store | Immediately | Apply schema and verify auth bootstrap |
| Cloud Run | Production hosting target | Soon | Define deployment contract and secret handling |
| Voice/avatar providers | Future interaction channels | Later | Approve architecture after text baseline is stable |

---

## Current State Snapshot

What already exists in the repo:

- FastAPI runtime for chat, tasks, events, approvals, corrections, artifacts, and admin APIs
- Supabase-compatible persistence layer for operational and governance records
- Machine API key auth and admin JWT auth flow
- Import/install flow for generic twin packages derived from `agent-kernel`
- Basic browser chat UI at `/` and admin UI at `/admin`
- Test coverage for installability, runtime behavior, auth, and admin governance

What is not done yet:

- Local end-to-end validation against a real Supabase project
- Production deployment workflow for Cloud Run
- Structured operational observability for production incidents and performance
- Realtime voice transport, voice session management, or avatar rendering

---

## Planning Matrix

| Category | 30 Days — Immediate | 60 Days — Soon | 90 Days — Long Term |
|---|---|---|---|
| **Learn** | Confirm where local setup breaks with real Supabase auth, schema, and machine/API-client flows | Learn Cloud Run operational limits for the text runtime, startup import flow, and secret/bootstrap handling | Learn realtime media, transcript sync, interruption handling, and avatar channel constraints |
| **Analyze** | Identify the smallest set of fixes needed to make local text chat and agent interactions stable | Analyze deployment topology: Cloud Run service, secrets, install strategy, logs, metrics, and rollback | Analyze voice/avatar providers and select the pilot stack without coupling the twin brain to the media layer |
| **Implement** | Run locally with Supabase, fix gaps, tighten docs, and add missing tests for the local path | Deploy to Cloud Run, add observability, deployment scripts, and production-safe startup behavior | Add voice session bootstrap, transcript persistence, and then a controlled avatar pilot |
| **Relationships** | Align the runtime behavior to the Principal Operator’s expectations for identity, governance, and correction speed | Align deployment and secret management with the intended GCP project and operating model | Align avatar and voice choices with the intended user experience and cost/risk envelope |

---

## 30-Day Plan: Local Supabase Validation

**Goal:** prove the current text runtime works locally with Supabase before any deployment work.

### Work Items

1. Apply [`supabase/schema.sql`](/Users/fszale/projects/agent-factory/supabase/schema.sql) to a real Supabase project.
2. Set and verify:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_JWT_SECRET`
   - `XAI_API_KEY`
   - `AGENT_FACTORY_REQUIRE_AUTH=true`
3. Import and install the desired twin package from `agent-kernel`.
4. Bootstrap the first admin identity:
   - create Supabase Auth user
   - insert that user into `admin_identities`
5. Run the API locally and validate:
   - `/health`
   - `/me`
   - `/twins`
   - `/threads` create/list/message flow
   - `/tasks` create/list flow
   - `/approvals`, `/corrections`, `/artifacts`
   - `/api-clients` creation from `/admin`
6. Exercise one end-to-end governance loop:
   - bad answer or correction captured
   - correction recorded
   - artifact proposal created
   - audit event visible
7. Add or tighten any missing tests discovered during local validation.

### Exit Criteria

- One installed twin can chat locally against a real model and persist the conversation in Supabase.
- One machine API client can call the runtime with the expected scopes.
- One admin can log in, review governance data, and create or inspect API clients.
- Any local defects discovered have either been fixed or converted into tracked follow-up work with severity.

### Likely Gaps to Expect

- Supabase JWT/auth bootstrap friction
- CORS or browser token-handling issues in the local UI
- Schema mismatches or permissive assumptions in the in-memory test path that do not hold in Supabase
- Missing operational diagnostics when something fails in the auth/governance path

---

## 60-Day Plan: Cloud Run Production Baseline

**Goal:** deploy the stable text runtime to Cloud Run only after the local Supabase path is proven.

### Work Items

1. Define the deployment contract:
   - how twins are imported or installed at build/startup
   - where secrets live
   - what env vars are required
2. Add Cloud Run deployment artifacts:
   - deployment script or infra manifest
   - service config for env vars and concurrency
   - secret wiring for Supabase and xAI
3. Add production observability:
   - structured logs
   - request correlation IDs
   - error classification
   - latency and throughput metrics
4. Add production hardening:
   - health/readiness expectations
   - startup validation for required secrets
   - rate limiting and cost guardrails
5. Validate production governance:
   - admin auth works in deployed environment
   - machine clients are scoped correctly
   - audit history survives redeploys

### Exit Criteria

- Cloud Run hosts the runtime successfully with Supabase persistence and authenticated access.
- The installed twin is reachable through text chat and programmatic APIs.
- Basic observability exists for request tracing, failures, and usage.
- Rollback and configuration changes are operationally straightforward.

---

## 90-Day Plan: Voice and Avatar Pilot

**Goal:** add voice first, avatar second, without turning the media channel into the system-of-record.

### Recommended Architecture

- `agent-factory` remains the control plane for auth, governance, persistence, and tool/task routing
- Supabase remains the system-of-record for sessions, transcripts, approvals, corrections, and audit
- Voice is added as a separate realtime media plane
- Avatar is treated as a channel layered on top of the same twin runtime, not a separate brain

### Voice Sequence

1. Add voice session bootstrap endpoints to `agent-factory`.
2. Persist voice sessions and transcript segments in Supabase.
3. Add interruption/barge-in and transcript reconciliation rules.
4. Add admin visibility into voice session history and governance events.

### Avatar Sequence

1. Keep avatar disabled until voice behavior is stable.
2. Add avatar session metadata and channel controls in the twin manifest.
3. Run a limited pilot focused on:
   - latency
   - transcript fidelity
   - behavior consistency with the text twin
   - operator correction speed

### Guardrails

- No separate prompt stack for avatar beyond channel-level formatting or delivery instructions
- No direct self-modification from voice or avatar sessions
- All corrections still flow through the same correction and artifact-governance pipeline

---

## Pareto Priorities (20% that delivers 80% of value)

**30-Day Pareto Priority (1–2 items):**

> Get one installed twin running locally against real Supabase and real auth, then close the gaps that block normal chat, task, and governance flows.

**60-Day Pareto Priority (1–2 items):**

> Deploy only the text runtime to Cloud Run with reliable secrets, logs, and rollback; do not mix in voice/avatar work at this stage.

**90-Day Pareto Priority (1–2 items):**

> Add voice session support as a thin channel over the existing runtime, then decide whether avatar adds enough value to justify its operational cost.

---

## Value Stream Tagging

| Item | Value Stream | Horizon |
|---|---|---|
| Local Supabase validation | 🛡️ Risk / 💸 Cost | 30 |
| Cloud Run deployment baseline | 🛡️ Risk / 💸 Cost | 60 |
| Governance workflow hardening | 🛡️ Risk | 30 / 60 |
| Voice pilot | 💰 Revenue / 🛡️ Risk | 90 |
| Avatar pilot | 💰 Revenue / 💸 Cost | 90 |

---

## PPT Impact

| Dimension | Immediate Impact | Soon Impact | Later Impact |
|---|---|---|---|
| **People** | Principal Operator validates behavior and governance directly | Admin/governor workflows become usable in deployed environments | End users gain voice/avatar interaction channels |
| **Process** | Local bootstrap and testing process becomes repeatable | Deployment, rollback, and monitoring become operationalized | Realtime interaction and transcript governance become standardized |
| **Technology** | Supabase-backed auth and persistence are proven | Cloud Run hosting and observability are added | Voice/avatar stack integrates as optional channels |

---

## Success Metrics

| Horizon | Done Looks Like | Metric | Target Value | Expected Rate of Improvement |
|---|---|---|---|---|
| 30 days | Local runtime works with real Supabase and admin bootstrap | End-to-end local validation scenarios completed | 100% of critical scenarios pass | Front-load most failures into week 1 and taper sharply by week 3 |
| 60 days | Production-like Cloud Run environment is stable | Deployment success rate and critical incident count | 1 stable environment, 0 unresolved critical incidents | Deployment friction should decline each release |
| 90 days | Voice is piloted safely and avatar is decision-ready | Voice session success rate and operator correction latency | 1 controlled pilot, correction latency within acceptable operator threshold | Quality should improve gradually with tighter session instrumentation |

---

## Dependency Map

| Before This (30-day task) | This Must Complete | So That (60-day task) Can Begin |
|---|---|---|
| Supabase schema applied | Real local auth and persistence test | Cloud Run secrets and startup can be validated confidently |
| Twin imported and installed | Local text/chat/task verification | Production deployment can carry a known-good twin package |
| Admin bootstrap proven | Governance loop exercised locally | Admin governance can be trusted in production |
| Local defect list reduced | Runtime hardening and docs updates | Deployment work does not chase avoidable local issues |

---

## Weekly Review Commitment

**Review cadence:** Weekly during local validation; then per deployment milestone  
**Review attendees:** Principal Operator plus any implementation contributors  
**Escalation trigger:** Any blocker that prevents local auth, Supabase persistence, or installed-twin execution for more than one working session

---

## Recommendation

Do not start voice or avatar implementation until the local Supabase-backed text runtime is proven. The fastest path to value is:

1. Validate local Supabase and auth end to end.
2. Fix the issues surfaced by that validation.
3. Deploy the text runtime to Cloud Run.
4. Add voice as the next channel.
5. Add avatar only if the voice pilot proves the interaction model is worth the extra operational surface area.
