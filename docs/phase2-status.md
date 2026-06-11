# Phase 2 Status — MCP Peer Interface + Improvement Loop

> Updated: 2026-05-29. Scope: `agent-factory`. Reads `agentic-playbook` (metric framing) and the `digital-twin-factory` design specs.

## What shipped

| Capability | Module | Status | Notes |
|---|---|---|---|
| Peer-capable MCP server | `agent_factory/mcp.py` | DONE | JSON-RPC 2.0. Serves tools (vertical) + agent delegation (horizontal). **Tasks primitive** (async, durable, retry + expiry). **Signed context** (HMAC) verified on receipt. Delegation routes through the **same autonomy/HITL policy** as a human task — `always_gate` actions stay gated (no privilege escalation). Exposed over HTTP at `POST /mcp`. |
| Trace capture | `tools.py` + `persistence.py` | DONE | Every tool dispatch writes a structured `trace` (task, action, outcome, signals incl. provider + usage). New tables: `traces`, `roi_snapshots`, `improvement_candidates`, `improvement_events` (InMemory + Supabase + `schema.sql`). |
| Scoring + RoI engine | `agent_factory/metrics.py` | DONE | Python impl of the **6-component usefulness score** + `score_confidence`, improvement-vs-baseline, weekly RoI delta, useful-completion-rate, and **curve classification** (s_curve / rise_decline / flat / investigate / baseline_forming). |
| Reflect → propose loop | `agent_factory/improvement.py` | DONE | Scheduled-style reflect job scores recent traces, finds low-scoring skill areas (narrow: 2–3 skills), and emits `improvement_candidates` + a **proposed kernel edit as a PR**. `PRPublisher` interface; **DryRunPRPublisher** writes diff + PR body (no repo writes, no token). `GitHubPRPublisher` staged behind a token. **Never auto-merges.** |
| Dashboard v1 | `metrics_service.py` + `app.py` | DONE | Endpoints: `GET /dashboard/hitl-queue`, `GET /metrics/ops` (tasks, success rate, corrections/task, cost/task by provider, mean usefulness), `GET /metrics/roi` (curve from live snapshots), `GET /improvements`, `POST /improvements/reflect`. HITL approve/reject/edit reuses the existing `/approvals/{id}/resolve`. |
| CLI | `cli.py` | DONE | `factory reflect --registry-root … --twin-id …` runs the loop and writes dry-run PRs. |

## Reality note (vs the plan)

Plan §7 / Phase 2 step 4 say to **port the "tested TypeScript ROI engine + 6-dimension scorer"** from `digital-twin-factory`. On inspection that repo contains the **design specs** (`docs/rate-of-improvement.md`, `docs/self-improvement.md`), not shipped tested code. So this is a faithful **Python implementation** of those exact formulas rather than a port. Flagging per the Phase 0 "reality vs claims" discipline.

## Done-when criteria (from the workflow)

- [x] One factory/peer can delegate a task to a twin over MCP, **under policy, with a durable task record** — `tests/test_mcp.py` + e2e over `POST /mcp` (auto-allow runs; `always_gate` stays gated).
- [x] The loop opened at least one real, sensible improvement PR (reviewed as a dry-run diff against `first-principles/SKILL.md`) — `tests/test_improvement.py` + e2e.
- [~] Dashboard shows the rate-of-improvement curve from live data — endpoints serve it from stored snapshots; the React view consuming them is the remaining UI step (data contract is live).

## Tests

81 passing (61 prior + 20 new): `test_metrics`, `test_improvement`, `test_mcp`, `test_dashboard_api`.

## Follow-ups (Phase 3 / hardening)

- Swap `DryRunPRPublisher` → `GitHubPRPublisher` once a `GITHUB_TOKEN` is set (diff + PR body already produced).
- Render the dashboard React view against the new metrics endpoints (port from `digital-twin-factory` UI).
- A scheduled weekly job to write `roi_snapshots` automatically (uses `build_roi_snapshot`); currently snapshots are written on demand.
- Move the in-process MCP `LocalScheduler`/task worker to the cloud `Queue`/`Scheduler` impls for multi-node durability.

## Rationalization

| Decision | Score | Why |
|---|---|---|
| PR-gated improvement, never auto-merge | 9/10 | Matches plan §6/§9; safe, auditable, demoable. Dry-run default removes all repo-write risk this session. |
| Implement RoI engine in Python vs "port" TS | 8/10 | The TS engine doesn't exist as code; reimplementing from the spec is lower-risk than chasing a phantom port. −2: a future TS UI may want shared logic — acceptable, the formulas are small. |
| Delegation reuses the Phase-1 autonomy gate verbatim | 9/10 | One policy path for human + peer tasks; `always_gate` provably holds under delegation. Risk-weighted: high-value invariant, directly tested. |
| In-process Tasks worker for now | 7/10 | Proves the primitive end-to-end; −3 it's single-node until wired to cloud Queue. Clean swap, interfaces already exist. |
