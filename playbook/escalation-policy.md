# Escalation Policy

## Risk levels

Provisioning-driven severity is gated by **ownership**, not just by how many
days overdue something is. This is deliberate: a `cs`-owned bottleneck has no
autonomous remediation available regardless of how stale it gets, so escalating
it to HIGH wouldn't change what the agent can do about it. A `customer`-owned
overdue step is different -- it's the exact condition that makes an autonomous
nudge both safe and useful, so it's what actually earns HIGH.

- **HIGH** — any of: invoicing-policy issuance-window breach; two or more
  overdue provisioning steps where at least one is `customer`-owned; any
  `customer`-owned overdue step more than 7 days past due.
- **MEDIUM** — any of: invoicing-policy payment-window breach; provisioning
  blocked on one or more `cs`-owned overdue steps with no `customer`-owned
  step overdue.
- **LOW** — nothing overdue, invoice on track relative to policy windows.

## How risk_level and recommended_action combine

These two fields are read independently by the n8n Switch, not as alternatives:

- **`risk_level` drives notification.** `medium` or `high` always triggers a
  Slack notification with the LLM's summary. `low` never notifies (the agent
  should not cry wolf on healthy accounts).
- **`recommended_action` drives the additional autonomous system action**, on
  top of whatever notification `risk_level` already triggered. `none` means no
  extra action. `nudge_customer` and `create_task` are the only two values
  that can trigger a real action, and only if they pass the allowlist check
  below.

So a HIGH-risk account with an overdue customer-owned step gets **both** a
Slack notification (from risk_level) **and** an autonomous nudge (from
recommended_action) in the same run.

## Autonomous action allowlist

Only these actions may be executed without human approval. Everything else
must route to a human via Slack notification.

1. **`nudge_customer`** — send a templated reminder via `POST
   /provisioning/nudge`, and only for provisioning steps that are (a) overdue
   and (b) owned by `customer`. Idempotent per customer per day — a repeat
   nudge on the same day is a no-op that returns the existing nudge id.
2. **`create_task`** — logged to the audit trail as a recommended follow-up for
   the CS team. **Not auto-executed** in this prototype (no ticketing system
   is mocked yet) — it is recorded but always paired with a Slack
   notification so a human picks it up. This is a known scope cut, not a bug.

Every other risk (invoicing breaches, `cs`-owned bottlenecks, anything
ambiguous) maps to `recommended_action: "notify"` — Slack only, no autonomous
system action.

## Summary table

| Condition                                                        | risk_level | recommended_action |
|--------------------------------------------------------------------|------------|---------------------|
| Nothing overdue, invoice on track                                  | low        | none                |
| Invoice issued, unpaid past 15-day window, no overdue steps         | medium     | notify              |
| Provisioning blocked on `cs`-owned overdue step(s) only              | medium     | notify              |
| Invoice not created past 5-business-day window                      | high       | notify              |
| Overdue `customer`-owned provisioning step(s), invoice OK            | high       | nudge_customer      |
