# Workflow: review the HITL approval queue

Goal: clear the pending approval queue without rubber-stamping anything.

Prereqs:

- You're an operator with approval scope on this factory.
- You're authenticated in the dashboard.

## Steps

1. **Open the queue**
   - Go to `/admin/approvals`. The "Pending" tab shows the queue with the
     count next to it.

2. **Read the action and summary**
   - Each card shows the twin, the action label
     (e.g. `send.email`, `publish.post`), and a one-line summary.
   - Expand the JSON payload underneath if you need the exact arguments.

3. **Decide deliberately**
   - Type a note in the textarea explaining why. Even one word
     ("approved per playbook §4") helps future you.
   - Click **Approve** or **Reject**. The card updates immediately
     (optimistic) and the dashboard records your decision.
   - If the API rejects the call, the card rolls back to pending and a
     destructive toast explains why.

4. **Spot-check via audit**
   - Open `/admin/audit?action=approval.accept` (or `approval.reject`).
   - Your decisions are visible with your actor label and the note in
     metadata.

5. **Triage stuck items**
   - If a pending row hasn't been decided in `>1h` and the twin keeps
     waiting, escalate to the twin owner. Approvals do **not** auto-expire
     by design — silence is not approval.

## Bulk-decide

Today the UI is one row at a time on purpose: every decision should be a
real decision. If you find yourself wanting bulk actions, that's a signal
the twin spec is too eager — adjust the spec to ask for fewer approvals
instead of building bulk-approve into the queue.

## When to escalate

- Approval payload mentions a customer / dollar amount you don't recognize
  → reject and ping the twin owner.
- A twin keeps surfacing the same approval pattern → consider hardcoding
  the safe shape into the twin spec or adding a guardrail.
- Decision API repeatedly errors with `409 Conflict` → another operator
  decided it; refresh the page.

## Read also

- `.agents/skills/hitl-governance/SKILL.md` — the governance invariants the
  queue exists to enforce.
- `.agents/skills/audit-review/SKILL.md` — how to read the resulting audit
  rows.
