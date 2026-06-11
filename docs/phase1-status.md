# Phase 1 Status — Twin-Builder CLI + Autonomy

> Updated: 2026-05-29. Scope: `agent-factory`. Builds on the Phase 0 audit.

## What shipped

| Capability | Module | Status | Notes |
|---|---|---|---|
| Bridge contract loader | `agent_factory/bridge.py` | DONE | Pydantic models for `twin.yaml`; enforces pinned semver tag, name pattern, and "full-autonomy requires guardrails". |
| Twin-builder `build` | `agent_factory/builder.py` | DONE | Validates bridge → resolves pinned kernel (git clone at tag w/ private-repo auth, or local checkout) → layers overrides → emits **content-addressed immutable artifact** + `build.manifest.json`. Runtime loads the artifact, never raw repos. |
| Twin-builder `deploy` | `agent_factory/deploy.py` | DONE | `factory twin deploy <artifact> --cloud gcp\|aws\|local`. Uploads via `Blob`, installs into registry, writes a deploy record. Cloud-agnostic. |
| Cloud interfaces | `agent_factory/cloud.py` | DONE | `Scheduler`, `Queue`, `SecretStore`, `Blob` with local in-process impls. ~5 interfaces = the Pareto cut for multi-cloud. |
| Deploy modules | `deploy/gcp/main.tf`, `deploy/aws/main.tf` | DONE (thin) | Map roles → Cloud Run/Scheduler/Tasks/GCS and ECS/EventBridge/SQS/S3. One Dockerfile. |
| Capability model router | `agent_factory/router.py` | DONE | Routes capability (research/social/engineering) → profile. No hardcoded models. |
| OpenAI provider | `agent_factory/providers/openai.py` | DONE | For the `research` route. Extracts real token usage. xAI + stub now also report usage. |
| Budget/usage meter | `agent_factory/autonomy.py` | DONE | Atomic token+USD counters per twin/day. **Hard-stop BEFORE the provider call returns** (preflight estimate) + post-call reconcile that pauses the twin on a crossed daily limit. |
| Kill switch | `agent_factory/autonomy.py` | DONE | Per-twin + factory-wide pause flags, checked at top of every dispatch. |
| HITL gate | `agent_factory/autonomy.py` + `tools.py` | DONE | propose-then-confirm forced by default; `always_gate` (send/post/purchase/deploy) gated even in full-autonomy. |
| Real tools | `agent_factory/tools.py` | DONE | `reminder` (scheduler-backed, **actually fires**), `search` (Grok), `research` (GPT), `engineer` (proposes a gated repo change). All dispatched through the autonomy gate. |
| Dogfood | `digital-twin-filip/twin.yaml` | DONE | Filip's bridge contract added; builds through the pipeline against pinned `agent-kernel v1.0.0`. |

## Done-when criteria (from the workflow)

- [x] A deliberate runaway test trips the daily limit and auto-pauses the twin — `tests/test_tools.py::test_runaway_trips_daily_limit_and_autopauses`.
- [ ] Use your own twin daily for a week without babysitting — operational, runs after deploy to a real cloud target with live API keys.

## Tests

41 passing (14 prior + 27 new): `test_bridge`, `test_builder`, `test_deploy`, `test_autonomy`, `test_router`, `test_tools`.

## Follow-ups (carry to Phase 2)

- Swap the local `Scheduler`/`Queue`/`Blob` impls for SDK-backed ones once a cloud target is provisioned (interfaces already in place).
- Persist budget counters in Postgres for multi-process atomicity (current meter is in-process; method surface matches a DB-backed swap).
- Wire the tool dispatcher + kill switch into the FastAPI hot path (`app.py`) and the dashboard HITL queue.

## Rationalization

Score 8/10: closes every Phase 0 must-close gap additively. The load-bearing 20% (reminder-that-fires + budget kill-switch) is tested and rock-solid. −2: budget meter is in-process (single-node) and cloud impls are interface-stubbed pending a provisioned target — both deliberate, both are clean swaps, neither blocks daily dogfooding on one node.
