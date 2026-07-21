# Solution Design — CS Onboarding Agent

**Scenario 1: Sales / Customer Success onboarding.** The job description names Salesforce and NetSuite
explicitly and calls out "customer onboarding" as a target domain, mirroring StackAdapt's own
quote-to-onboard stack. My solution is an n8n-orchestrated agent that monitors onboarding health
across four mocked systems both autonomously and conversationally, using a deterministic rules
engine for risk classification and Claude for narration and conversation — satisfying the
brief's mock-API-integration, LLM-generated-summary, and error-handling requirements directly,
plus its ask for both autonomous and interactive operation.

## Architecture

Docker Compose runs three pieces: **n8n** (orchestration), a **FastAPI** mock of
Salesforce/CLM/NetSuite/provisioning plus Slack and a SQLite audit trail, and the **Anthropic
API (Claude Sonnet 5)** for two distinct LLM roles — narrating a pre-computed verdict in Monitor,
and powering the full conversational agent in Chat. Three n8n workflows:

- **Monitor** (autonomous) — a Webhook (event-driven, fired on simulated `contract_signed`/
  `invoice_paid`) and a Schedule Trigger (twice daily — matched to the multi-day
  timescale of real onboarding) both feed the same assessment
  chain. The schedule sweep pulls its customer list from a live `GET /salesforce/opportunities`
  endpoint, so newly signed customers are automatically included.
- **Chat** (conversational) — an AI Agent (Claude Sonnet 5) with two tools and session memory.
- **Error Handler** — attached to both workflows' error-workflow setting; failures are logged to
  the audit trail and posted to `#ops-alerts` mock slack channel.

## How the AI agent is applied

Core principle: **the LLM narrates, code decides.** `Classify` is a deterministic function
(thresholds config-driven via `playbook/rules.json`, not hardcoded) computing `risk_level`/
`recommended_action`/`risks` from structured state — business-day issuance math, payment-window
math, ownership-gated overdue logic. The LLM is never asked to classify; it writes a summary of a
verdict it didn't produce, and is explicitly told not to change it. This isn't a compromise — the
exercise brief treats "LLM or rules-based logic" as alternatives, and structured inputs with crisp
thresholds are a better fit for code than inference, confirmed empirically: an earlier LLM-driven
version of this same classification miscounted business days and once produced an inconsistent
notify/nudge decision the deterministic version doesn't.

The exercise brief's four example applications of the AI agent all show up concretely:

- **Generating human-readable summaries.** `LLM Narrate` (Monitor) writes `summary`/`reasoning`
  from the pre-computed verdict, skipped entirely when `recommended_action === "none"` (cutting
  LLM calls for customers who are on track, since a clean account needs no narrative at all). Chat's
  AI Agent writes every reply conversationally.
- **Enriching details.** Chat's `get_customer_state(customer_id)` tool merges four separate
  systems (Salesforce, CLM, NetSuite, provisioning) into one view on demand.
- **Handling errors.** A dedicated Error Handler workflow catches uncaught failures from either
  workflow, logs them to the audit trail, and posts to `#ops-alerts` — separate from the retry
  logic on individual calls (see Trade-offs).
- **Taking actions.** The one side-effecting action (`nudge_customer`) is allowlisted and
  independently re-verified: nudge eligibility (customer-owned, overdue, not done) is re-derived
  from live data by code in both Monitor and Chat, never trusted from the LLM's own claims. Chat's
  action is additionally confirmation-gated at the code level — `draft_nudge(customer_id,
  confirmed)` only calls `/provisioning/nudge` when `confirmed: true`, and no code path reaches
  that call without a prior human turn.

## Orchestration

- **Event-driven triggers.** A Webhook reacts to simulated `contract_signed`/`invoice_paid`
  events; a Schedule Trigger independently sweeps every customer twice daily.
- **API/webhook flows.** Every inter-system call is plain REST against the mock API; actions
  (Slack post, nudge, audit write) are themselves POST calls, gated behind deterministic `IF`
  nodes reading the classification, never behind the LLM's own judgment about whether to act.
- **Middleware.** n8n is the only middleware layer. A `Normalize Trigger` step converts whichever
  trigger fired into one consistent shape immediately, so every node downstream is trigger-
  agnostic — branching logic never special-cases "did this come from the webhook or the
  schedule."

## Trade-offs and assumptions

**Reliability.** The NetSuite mock deliberately fails ~20% of calls (`FLAKY_RATE=0.2`) so the
system has a real transient failure to survive, not just a claimed one — the demo's concrete
answer to the brief's "logging or error handling approach" requirement. Retries (3 tries, fixed
delay — not true exponential backoff, a known simplification) apply to read-only calls and the
one idempotent action (`/provisioning/nudge`, keyed per customer/day); deliberately not to
`/slack/notify` or `/audit`, since blind retries on non-idempotent calls risk duplicate side
effects.

**Accepted repetition, not a bug.** An unresolved high-risk account gets re-notified on every
schedule tick; deduping would need per-customer state tracking, scoped out rather than built
speculatively. The nudge action doesn't share this problem — its idempotency is server-side.

**Security.** Secrets are never committed; the mock APIs themselves have no authentication — a
reasonable cut for a local prototype whose real risk surface is agent behavior, not endpoint
access, but production would need signed webhooks or mTLS on every one of these calls.

**Governance.** Every run — autonomous or chat-initiated — writes trigger source, full state
snapshot, and verdict to the audit trail as a first-class feature.

**Scalability.** SQLite and one n8n instance suit 3 customers and one sweep. Real volume would
need a proper database, queued sweeps instead of fetch-all-then-fan-out, and n8n's own scaling
story past a few hundred customers.

**Playbook scale.** The 3 policy docs here are short enough to inject in full on every narration
call. A real playbook with dozens of policies across product tiers and exceptions would break
that — full-text injection would blow past context budgets and bury the few relevant rules in
noise. At that point, RAG (chunking the playbook into a vector store and retrieving only the
sections relevant to a given customer's actual risks) is the right fix for `LLM Narrate`'s
context. It wouldn't help `Classify`, though — its structured thresholds (`rules.json`) are read
by field, not searched as text, so that side would scale via a proper rules/config service
instead, not a vector store.

## MCP collaboration overview

Each mocked system is a natural MCP server candidate — a standard tool interface any agent, not
just this one, could call. Chat's two tools are effectively a preview of that interface today,
built directly against the mock REST API; formalizing them as MCP servers would let other agents
(an HR onboarding agent, a Legal contract-review agent) reuse the same customer-state and
safe-action surface instead of re-implementing bespoke integrations. Audit/Slack are logging
sinks, not collaboration surfaces, and would likely stay plain REST.

---

## Appendix: Workato mapping

| n8n pattern | Workato equivalent |
|---|---|
| Webhook / Schedule Trigger | Recipe trigger (webhook / scheduled recipe) |
| HTTP Request node | Application or HTTP connector action |
| Code node (Classify, correlation lookups) | Formula/custom code step |
| IF node (Should Notify?/Should Nudge?) | Recipe conditional step |
| Error Handler workflow | Recipe error handling / exception recipe |
| AI Agent + tools (Chat) | Workato's AI-agent-in-a-recipe with connector actions as tools |
