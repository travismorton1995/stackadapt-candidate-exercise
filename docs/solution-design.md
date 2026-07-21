# Solution Design — CS Onboarding Agent

**Scenario 1 (Sales/CS onboarding).** The JD names Salesforce and NetSuite explicitly and calls
out "customer onboarding" as a target domain — this scenario mirrors StackAdapt's own
quote-to-onboard stack directly.

## Architecture

Docker Compose runs three pieces: **n8n** (orchestration), a **FastAPI** mock of
Salesforce/CLM/NetSuite/provisioning plus Slack and a SQLite audit trail, and the **Anthropic
API** for the one place an LLM is actually needed. Three n8n workflows:

- **Monitor** (autonomous) — a Webhook (event-driven, fired on simulated `contract_signed`/
  `invoice_paid`) and a Schedule Trigger (`0 7,15 * * *`, twice daily — matched to the multi-day
  timescale of real onboarding, not a demo-compressed interval) both feed the same assessment
  chain. The schedule sweep pulls its customer list from a live `GET /salesforce/opportunities`
  endpoint rather than a hardcoded list, so a newly signed customer is automatically included.
- **Chat** (conversational) — an AI Agent (Claude Sonnet 5) with two tools and session memory.
- **Error Handler** — attached to both workflows' error-workflow setting; failures are logged to
  the audit trail and posted to `#ops-alerts`.

## How the AI agent is applied

Core principle: **the LLM narrates, code decides.** `Classify` is a deterministic function
(thresholds config-driven via `playbook/rules.json`, not hardcoded) computing `risk_level`/
`recommended_action`/`risks` from structured state — business-day issuance math, payment-window
math, ownership-gated overdue logic. The LLM is never asked to classify; it writes a summary of a
verdict it didn't produce, and is explicitly told not to change it. This isn't a compromise — the
brief treats "LLM or rules-based logic" as alternatives, and structured inputs with crisp
thresholds are a better fit for code than inference, which we confirmed empirically: an earlier
LLM-driven version of this same classification miscounted business days and once produced an
inconsistent notify/nudge decision the deterministic version doesn't.

Same discipline for actions: nudge eligibility (customer-owned, overdue, not done) is re-derived
from live data by code in both Monitor and Chat, never trusted from the LLM's own claims. Chat's
one side-effecting action is confirmation-gated at the code level — `draft_nudge(customer_id,
confirmed)` only calls `/provisioning/nudge` when `confirmed: true`, and no code path reaches that
call without a prior human turn. The LLM handles narration (`summary`/`reasoning`, skipped
entirely when `recommended_action === "none"`, cutting LLM calls roughly in half per sweep) and
the full conversational surface, including enrichment (`get_customer_state` merges 4 systems into
one view on demand).

## Orchestration

Webhook, schedule, and chat triggers all converge on the same per-customer chain — trigger type
is normalized away immediately so downstream branching never special-cases it. All inter-system
calls are plain REST against the mocks; n8n is the only middleware. Actions are POST calls gated
behind deterministic `IF` nodes reading the classification, never behind the LLM's own judgment.

## Trade-offs and assumptions

**Reliability.** The NetSuite mock deliberately fails ~20% of calls (`FLAKY_RATE=0.2`) so the
system has a real transient failure to survive, not just a claimed one — this is the demo's
concrete answer to the brief's "logging or error handling approach" requirement. Retries (3
tries, fixed delay — not true exponential backoff, a known simplification) apply to read-only
calls and the one idempotent action (`/provisioning/nudge`,
keyed per customer/day); deliberately not to `/slack/notify` or `/audit`, since blind retries on
non-idempotent calls risk duplicate side effects.

**A concurrency bug worth naming.** Adding the multi-customer schedule sweep alongside the
single-customer webhook path surfaced a real issue: n8n's implicit node-reference resolution
isn't reliable once several items flow through divergent branches in one execution — it silently
dropped one customer's item and duplicated another's before we understood it. Fix: every
cross-node reference downstream of classification now uses an explicit `customer_id` correlation
lookup instead of implicit item-pairing — the same principle any distributed system uses to
correlate async results.

**Accepted repetition, not a bug.** An unresolved high-risk account gets re-notified on every
schedule tick; deduping would need per-customer state tracking, scoped out rather than built
speculatively. The nudge action doesn't share this problem — its idempotency is server-side.

**Security.** Secrets are never committed; the mock APIs themselves have no authentication — a
reasonable cut for a local prototype whose real risk surface is agent behavior, not endpoint
access, but production would need signed webhooks or mTLS on every one of these calls.

**Governance.** Every run — autonomous or chat-initiated — writes trigger source, full state
snapshot, and verdict to the audit trail as a first-class feature, matching the JD's governance
emphasis directly.

**Scalability.** SQLite and one n8n instance suit 3 customers and one sweep. Real volume would
need a proper database, queued sweeps instead of fetch-all-then-fan-out, and n8n's own scaling
story past a few hundred customers.

## MCP collaboration overview

Each mocked system is a natural MCP server candidate — a standard tool interface any agent, not
just this one, could call. Chat's two tools are effectively a preview of that interface today,
built directly against the mock REST API; formalizing them as MCP servers would let other agents
(an HR onboarding agent, a Legal contract-review agent) reuse the same customer-state and
safe-action surface instead of re-implementing bespoke integrations. Audit/Slack are logging
sinks, not collaboration surfaces, and would likely stay plain REST.

## Workato mapping

| n8n pattern | Workato equivalent |
|---|---|
| Webhook / Schedule Trigger | Recipe trigger (webhook / scheduled recipe) |
| HTTP Request node | Application or HTTP connector action |
| Code node (Classify, correlation lookups) | Formula/custom code step |
| IF node (Should Notify?/Should Nudge?) | Recipe conditional step |
| Error Handler workflow | Recipe error handling / exception recipe |
| AI Agent + tools (Chat) | Workato's AI-agent-in-a-recipe with connector actions as tools |
