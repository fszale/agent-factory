# AGENTS.md — instructions for AI coding agents

This file gives AI coding agents (OpenAI Codex, Cursor agents, generic
"AGENTS.md"-aware assistants) the rules they need to work productively in the
`agent-factory` repo. Anthropic-specific guidance lives in
[`CLAUDE.md`](./CLAUDE.md). Deeper architectural context lives in
[`CONTEXT.md`](./CONTEXT.md).

---

## What this repo is

`agent-factory` is a FastAPI + Supabase backend that turns digital-twin spec
repos into governed AI employees. A React admin dashboard (mirrored under
`dashboard/`) is the operator-facing UI. See [`README.md`](./README.md) for
the full architecture diagram.

The two non-negotiable invariants are:

1. **Every risky action passes through HITL approval.** Twins do not execute
   side-effecting tool calls without a recorded human decision.
2. **Every state change is auditable.** Append to the audit log; never delete
   or rewrite history.

If a change you are considering would weaken either of these, stop and ask the
maintainer first.

---

## Operating rules

1. **Read before writing.** Always open `README.md` and the relevant
   `.agents/skills/*` skill before touching the area it describes. Skills
   encode the invariants in plain English.
2. **Prefer small diffs.** Keep PRs focused: one resource, one bugfix, or one
   skill at a time.
3. **Don't widen the API surface unnecessarily.** New endpoints belong in
   the OpenAPI / FastAPI route definitions and must be reflected in the
   dashboard's typed client (`dashboard/src/lib/agent-factory/client.ts`)
   and in the API table in `README.md`.
4. **Keep the dashboard mirror in sync.** When you change a route shape, also
   update `dashboard/src/lib/agent-factory/types.ts` and re-run the dashboard
   tests (`pnpm run test` from the dashboard's host project).
5. **Never commit secrets.** `.env` is git-ignored. Use Supabase service-role
   keys only on the server.
6. **Comments are for "why", not "what".** Code says what; comments explain
   choices reviewers cannot otherwise reconstruct.

---

## Planning a change

Before editing, write (in your scratch buffer, not a file) a short plan:

- **What's the user-visible change?**
- **Which routes / tables / skills are affected?**
- **What test(s) prove it works?**
- **Does it touch governance or audit?** (If yes, slow down.)

If the change is trivial (typo, dependency bump, docstring) skip the plan.

---

## Workflows

Repeatable multi-step tasks are documented under
[`.agents/workflows/`](./.agents/workflows/). Today there are two:

- **`import-and-deploy-twin.md`** — bring a new twin from a git URL to a live
  serving state.
- **`review-approvals.md`** — work the HITL approval queue end to end.

If you find yourself doing the same multi-step dance twice, write a workflow.

---

## Skills

Skills under [`.agents/skills/`](./.agents/skills/) are the canonical
instructions for working in a particular area. Read them before:

- **Twin lifecycle work** → `.agents/skills/twin-lifecycle/SKILL.md`
- **HITL approvals** → `.agents/skills/hitl-governance/SKILL.md`
- **Audit log queries / changes** → `.agents/skills/audit-review/SKILL.md`

Skills point to specific files, expected behaviors, and red-flag changes.

---

## House style

- **Python**: type-hint everything, use Pydantic v2 for I/O, prefer pure
  functions, return `None` rather than empty dicts.
- **TypeScript** (dashboard mirror): strict mode, no `any`, named exports.
- **Errors**: prefer raising `HTTPException` with the smallest meaningful
  status; never swallow errors silently.
- **Tests**: unit tests for pure logic (scoring, filters, status), HTTP-level
  tests for routes. The dashboard's pure-logic modules under
  `dashboard/src/lib/agent-factory/` are 100% test-covered.

---

## Where to put things

- New REST route → `agent_factory/api/<resource>.py`
- New persistence model → `agent_factory/db/models/<resource>.py`
- New twin lifecycle step → `agent_factory/twins/lifecycle.py`
- New HITL-touched action → must add an approval requirement
- Operator-facing UI change → in the Replit `digital-twin-portal` artifact
  under `src/pages/admin/`, then mirror back to `dashboard/`.

---

## Out of scope

Don't:

- Add a separate frontend framework. The single dashboard is React + Vite.
- Replace Supabase wholesale. If you need a different store, write a thin
  adapter and keep Supabase as a default.
- Bypass approvals "just for testing". Use the test-mode auto-approver
  documented in the HITL skill.

---

## When stuck

Open `CONTEXT.md` for the longer story, or surface a question in the PR
description. Filip prefers being asked over surprised.
