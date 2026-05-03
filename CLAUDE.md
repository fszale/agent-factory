# CLAUDE.md — Anthropic-specific guidance

This file gives Claude (Code, in chat, or via MCP) the conventions and
guardrails for working in `agent-factory`. The generic agent rules live in
[`AGENTS.md`](./AGENTS.md); deeper architectural context lives in
[`CONTEXT.md`](./CONTEXT.md). Read both.

## Mental model

`agent-factory` is a **factory for digital twins**. Twins are governed AI
employees defined by spec repos. The factory:

1. Imports a spec from git
2. Installs and registers it as a runnable twin
3. Hosts threaded conversations against it
4. Gates risky tool calls behind a human approval queue
5. Logs everything to an append-only audit table

Two invariants are sacred:

- **HITL approval gates risky actions.** Never bypass.
- **Audit log is append-only.** Never rewrite.

If a refactor would weaken either, surface that as a question instead of
shipping it.

## How Claude should work here

1. **Open the relevant skill first.** Skills in `.agents/skills/` encode what
   "good" looks like for each area. Read them before editing.
2. **Use TodoWrite for multi-step changes.** Plan import → install → serve as
   distinct steps with verification gates.
3. **Prefer small, reviewable diffs.** Keep one resource per PR.
4. **Echo invariants back when relevant.** When a change touches HITL or
   audit, mention which invariant it preserves in your PR description.
5. **Update the dashboard mirror together with the API.** Route shape changes
   require updating `dashboard/src/lib/agent-factory/types.ts` and re-running
   the dashboard tests in the same change.

## Tooling expectations

- **Tests**: unit-test pure logic; HTTP-test routes. The dashboard's
  `lib/agent-factory/*` modules are fully unit-tested — keep them that way.
- **Type safety**: strict TypeScript on the dashboard, Pydantic v2 on the
  backend.
- **Errors**: surface meaningful messages; the dashboard's `FactoryApiError`
  expects either `detail`, `message`, or `error` fields, plus FastAPI's
  validation `detail: [{msg}]` shape.

## Code-review checklist (Claude self-check)

Before opening a PR, confirm:

- [ ] No risky action newly executes without approval.
- [ ] No audit-log row is updated or deleted (only appended).
- [ ] Route shapes that changed are reflected in the dashboard types and tests.
- [ ] New behavior is documented in the affected skill or the README API table.
- [ ] No secrets in git.

## When asked to "make it work without HITL"

Decline. Offer the test-mode auto-approver documented in
`.agents/skills/hitl-governance/SKILL.md` instead. If the user insists, push
back and ask whether they want the test-mode behavior, or whether they're
trying to run a one-off operator action they should be doing through the
dashboard.
