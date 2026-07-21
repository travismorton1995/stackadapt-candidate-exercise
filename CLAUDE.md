# CLAUDE.md — CS Onboarding Agent (StackAdapt Candidate Exercise)

## What this project is

A candidate exercise for the "Enterprise Agent Solutions Developer" role at StackAdapt.
We are building **Scenario 1: a Customer Success onboarding agent** — an AI agent that
monitors client onboarding across a mocked SaaS stack (Salesforce CRM → CLM → NetSuite
ERP → SaaS provisioning), detects risks and stalls, notifies the CS team, and takes a
narrow set of safe autonomous actions. It also exposes a chat interface for CS users.

**Hard constraint: ~2 days total build time.** Deliverables: (1) a 1–2 page solution
design doc, (2) a working lightweight prototype, (3) a ≤5-minute demo recording.
The prototype bar (from the brief): demonstrate mock API integration, an LLM generating
a human-readable message, and a logging/error-handling approach. Mocks and dummy JSON
are explicitly acceptable.

## Why these choices (JD alignment — reference in the design doc)

- The job description names "customer onboarding" as a target domain and names
  Salesforce + NetSuite twice. Scenario 1 mirrors StackAdapt's own quote-to-onboard stack.
- JD asks for "conversational interfaces, context-aware workflows, and agentic task
  execution" → we build BOTH an autonomous monitor loop AND a chat entry point.
- JD lists "governance and audit" as a job duty → audit logging is a first-class feature.
- JD names Workato/Zapier as their platforms → we build in n8n (permitted by the brief)
  but the design doc must include a short section mapping our patterns to Workato
  equivalents (triggers→recipe triggers, error workflow→recipe error handling, etc.).
- JD wants Python proficiency → mocks are a real FastAPI app, not just n8n webhooks.
- JD emphasizes demos → the recording is treated as mandatory, structured as a
  stakeholder demo (business problem → agent catches stall → chat interaction → roadmap).

## Architecture

Everything runs locally via Docker Compose:

- **n8n** (self-hosted container, browser canvas at localhost:5678) — orchestration.
  Three workflows: (1) Monitor (autonomous loop), (2) Chat (agent with tools),
  (3) Error Handler (attached to both as their error workflow).
- **FastAPI mock server** (container, localhost:8000) — fake Salesforce / CLM /
  NetSuite / provisioning APIs backed by JSON fixtures, plus an /audit endpoint
  backed by SQLite, plus one deliberately flaky endpoint to demo retries.
- **LLM API** (external) — settled on the **Anthropic API (Claude Sonnet 5)**,
  via n8n's Anthropic Chat Model node. NEVER commit API keys. Use .env +
  .gitignore from the first commit; provide .env.example.

Key design principle (state it in the doc): **the LLM narrates, code decides.**
This went further than originally planned: classification itself
(risk_level/recommended_action/risks) is now a **deterministic Code node**
(`Classify`, in Monitor), not an LLM output — thresholds live in
`playbook/rules.json` so editing policy doesn't require touching code. The LLM
is only ever asked to write `summary`/`reasoning` for a verdict it didn't
produce, and is explicitly told not to change it. This was a deliberate
mid-build pivot (see design doc's trade-offs section for the full reasoning):
the brief treats "LLM or rules-based logic" as alternatives, and this system's
inputs are structured JSON with crisp thresholds, not open-ended text -- a
better fit for code than inference. An n8n IF-node chain (`Should Notify?`,
`Should Nudge?`) reads the classification and routes to notify vs. act,
constrained by an action allowlist re-verified independently of the LLM's
claims (nudge eligibility is recomputed from live data, never trusted as-is).

Playbook grounding: 3 short markdown policy docs injected directly into the
LLM's narration prompt (no vector store in core scope — see stretch goals),
plus `rules.json` as the structured source the deterministic classifier reads.

## Repo layout

```
/mocks            FastAPI app (main.py, routers per system), fixtures/*.json
/playbook         3 markdown policy docs (see below)
/workflows        exported n8n workflow JSON (user exports manually from canvas)
/docs             solution-design.md
docker-compose.yml
.env.example
README.md
CLAUDE.md         (this file)
```

## Division of labor

- **Claude Code builds:** everything file-based — FastAPI app, fixtures, playbook
  docs, docker-compose, design doc draft, README, helper scripts.
- **The user (Travis) builds by hand:** the n8n workflows on the browser canvas.
  Do NOT generate n8n workflow JSON for import — it is brittle. Instead, when asked,
  give node-by-node canvas instructions, and help debug by reading exported JSON or
  error output that Travis pastes in.

## Mock API spec (FastAPI, port 8000)

All GET endpoints read from fixtures/. Customer IDs: `acme`, `globex`, `initech`.

- `GET /salesforce/opportunities` → { customer_ids: [...] } — lists every
  customer with a fixture, by scanning fixtures/. Drives Monitor's Schedule
  Trigger sweep so a newly signed customer is picked up automatically instead
  of needing a hardcoded list edited by hand.
- `GET /salesforce/opportunities/{customer_id}` → { customer_id, opportunity_stage,
  close_date, account_owner, contact_email, product_tier }
- `GET /clm/contracts/{customer_id}` → { customer_id, status
  (draft|sent|signed), signed_date, contract_value }
- `GET /netsuite/invoices/{customer_id}` → { customer_id, invoice_status
  (not_created|issued|paid), issued_date, paid_date, amount }
  **This endpoint is the flaky one: ~20% of calls return HTTP 500** (configurable
  via env var FLAKY_RATE, default 0.2; set to 0 for tests). This exists
  specifically to give the demo a real transient failure to survive, not a
  claimed one — it's the concrete answer to the brief's "logging or error
  handling approach" requirement (deliverable 2c). Mention in README.
- `GET /provisioning/status/{customer_id}` → { customer_id, steps: [ { name,
  owner (cs|customer), status (pending|in_progress|done), due_date } ] }
- `POST /provisioning/nudge` → { customer_id, message } → simulates sending a
  templated reminder to the customer contact; returns { sent, nudge_id,
  customer_id } (customer_id echoed back so n8n has a correlation key to look
  up the right record after the HTTP call replaces $json — see the
  correlation-ID note under n8n workflows).
  Must be **idempotent per (customer_id, day)** — repeat calls same day return the
  existing nudge_id with sent: false, "already_nudged". This is a talking point.
- `POST /slack/notify` → { channel, text, customer_id } → mock Slack; appends
  to a visible log. Also echoes customer_id back in its response, same reason
  as /provisioning/nudge above.
- `GET /slack/log` → view what's been posted (demo convenience, not in the
  original spec but implied by "visible log").
- `GET /playbook` → concatenated text of the 3 markdown policy docs, for the
  LLM's narration prompt.
- `GET /playbook/rules` → structured JSON (playbook/rules.json) the
  deterministic Classify node reads — issuance/payment window days, the
  customer-overdue-days HIGH threshold.
- `POST /audit` → { run_id, trigger, customer_id, state_snapshot, llm_verdict,
  action_taken, timestamp } → writes to SQLite (audit.db).
- `GET /audit` → list entries (for the demo: show the trail).
- `POST /webhooks/simulate/{event}` → helper that fires a webhook at n8n
  (contract_signed, invoice_paid) so events can be triggered on demand in the demo.

## Fixture design (the demo IS the fixtures)

- **acme** — the stalled customer. Contract signed 12 days ago; invoice not_created;
  provisioning untouched; two customer-owned steps overdue. → HIGH risk. Expected
  agent behavior: Slack notification with summary + autonomous nudge for the
  overdue customer-owned steps.
- **globex** — the healthy customer. Everything on track, provisioning 50% done
  (2 of 4 steps), nothing overdue. → LOW risk. Expected: log only, no
  notification. (Shows the agent doesn't cry wolf.)
- **initech** — the edge case. Invoice issued but unpaid past playbook threshold;
  provisioning blocked on a CS-owned step. → MEDIUM risk. Expected: notification,
  NO autonomous action (action is CS-owned, not on the allowlist).

**Known fragility (internal note — not for the design doc or README, per
Travis):** fixture due-dates are anchored to absolute calendar dates rather
than computed relative to runtime. globex's one `in_progress` customer step
actually drifted from "not yet due" into "overdue" between when these
fixtures were authored (2026-07-17) and when this was caught during Chat
workflow testing (2026-07-21) — real time passing alone flipped its intended
LOW-risk demo story to HIGH. Fixed by re-anchoring signed_date/due_dates with
a comfortable buffer (see `mocks/fixtures/globex_*.json`), but if the demo
recording happens significantly later than that fix, re-check all 3
fixtures' due_dates against the actual recording date before relying on them
— acme and initech aren't at the same risk (acme's issuance breach is
already exceeded by such a wide margin that further drift doesn't matter;
initech's customer-owned steps are fixture-marked `done` and can never
become overdue), but globex's buffer is finite.

## Playbook docs (markdown, injected into the prompt)

1. `invoicing-policy.md` — invoices issued within 5 business days of signature;
   payment expected within 15 days of issue.
2. `provisioning-checklist.md` — standard steps per product tier, expected
   durations, which steps are customer-owned vs CS-owned.
3. `escalation-policy.md` — what counts as low/medium/high risk; allowlisted
   autonomous actions (send templated nudge for overdue CUSTOMER-owned steps only;
   create follow-up task); everything else notifies humans.

## Classification and narration (Monitor workflow) — superseded design

**This section originally specified the LLM producing the full verdict
(risk_level + recommended_action + summary + reasoning) in one call. That
was rebuilt mid-project.** Classification is now a deterministic Code node
(`Classify`) evaluating `playbook/rules.json` thresholds against merged
customer state — no LLM involved, no ambiguity, fully unit-testable. The LLM
(`LLM Narrate`) is only given the pre-computed classification and asked to
write `summary`/`reasoning` from it, echoing back `customer_id` so its output
can be correlated to the right record downstream:

```json
{
  "customer_id": "the customer_id given to you, copied exactly",
  "summary": "2-3 sentence human-readable status for the CS team",
  "reasoning": "1-2 sentences citing the specific playbook rule(s) involved"
}
```

`LLM Narrate` is skipped entirely when `recommended_action === "none"` (via a
`Should Narrate?` IF node, falling through to a `Build Low-Risk Verdict` Code
node with static template text) — cuts LLM calls roughly in half across a full
customer sweep, since a clean account needs no narrative at all.

## n8n workflows (built manually on canvas — provide guidance when asked)

**Workflow 1 — Monitor** (as actually built, not the original plan):
Two triggers converge into the same chain via a `Normalize Trigger` Code node
(detects which trigger fired, outputs a consistent `{customer_id,
trigger_source}` regardless):
- Webhook Trigger, from /webhooks/simulate — single customer, event-driven.
- Schedule Trigger, cron `0 7,15 * * *` (twice daily — matched to the
  multi-day timescale of real onboarding, not the originally-planned 2-min
  demo interval) → `Get Customer List` (GET /salesforce/opportunities) →
  `Explode Customer List` (fan out to N items, one per customer).

`Normalize Trigger` → sequential (not parallel — simpler, and fine at this
scale) HTTP Request nodes for Salesforce/CLM/NetSuite/Provisioning/Playbook/
Rules Config (retry 3x fixed-delay on all GETs, not exponential backoff — a
known n8n limitation) → `Build State` (Set node merging everything) →
`Classify` (deterministic Code node) → `Should Narrate?` IF → [`LLM Narrate`
→ `Parse Narration`] or [`Build Low-Risk Verdict`] → `Merge Verdict` →
`Should Notify?` IF → [`Slack Notify`] → `Should Nudge?` IF → [`Send Nudge`]
→ `Write Audit`. Error Handler is attached via Monitor's own Settings →
Error Workflow, not an inline node.

**Important implementation note for future changes to this chain:** every
cross-node reference from `Classify` onward uses an explicit `$('NodeName')
.all().find(v => v.json.customer_id === $json.customer_id)` correlation
lookup, NOT `$node["NodeName"].json` or `$('NodeName').item.json`. This was a
real bug fix, not stylistic — n8n's implicit item-pairing proved unreliable
once the Schedule Trigger's multi-customer fan-out meant several items with
divergent branch paths flow through one execution concurrently (it silently
dropped one customer's item and duplicated another's before this was
understood). Don't revert to implicit references when adding new nodes here.

**Workflow 2 — Chat:**
n8n Chat Trigger (hosted chat UI) → AI Agent node (Claude Sonnet 5 + Simple
Memory) with 2 Code Tools: `get_customer_state(customer_id)` (chains the 4
GET endpoints, merges, returns as a JSON string) and
`draft_nudge(customer_id, confirmed)` (independently re-derives nudge
eligibility from live provisioning data — same rule `Classify` uses, never
trusts the LLM's own claims about eligibility; `confirmed: false` only
returns a preview and touches no side-effecting endpoint; `confirmed: true`
is required before it will POST /provisioning/nudge and log to /audit). Both
tools retry transient failures manually inside their own code (Code Tool
nodes have no built-in "Retry On Fail," unlike regular HTTP Request nodes).
System prompt includes the playbook docs and today's date (`$now` — omitting
this caused the agent to hedge with "if today is past X" instead of
reasoning definitively, a real bug caught and fixed). Error Handler is
attached the same way as Monitor's.

## Build order (thin slice first — protect against running out of time)

- **Phase 0 — done.** docker-compose with n8n + mocks skeleton; verified n8n
  can reach http://mocks:8000; .env/.gitignore/.env.example; git + GitHub.
- **Phase 1 — done.** mocks with acme + /slack/notify + /audit.
- **Phase 2 — done.** Monitor thin slice end-to-end for acme: trigger → state
  → LLM → notification → audit.
- **Phase 3 — done, and expanded beyond the original scope.** globex +
  initech fixtures; Switch branching + nudge action + idempotency; flaky
  endpoint + retries + error workflow — all as planned. Additionally
  (not originally scoped for this phase, added because the reasoning held up
  under scrutiny): classification moved from LLM to a deterministic
  config-driven Code node (see Architecture); a Schedule Trigger with a
  dynamically-fetched customer list, replacing the originally-hardcoded
  3-customer list; the explicit correlation-ID architecture fix described
  under n8n workflows above.
- **Phase 4 — done.** Chat workflow, 2 tools, human-confirmation-gated nudge.
- **Phase 5 — done.** Design doc (`docs/solution-design.md`), README, all 3
  workflows exported to `/workflows`.
- **Phase 6 — remaining.** Demo recording: problem → simulate contract_signed
  webhook → agent catches acme stall → show Slack log + audit trail → show
  retry surviving a 500 → schedule sweep catching all 3 customers → chat
  status query + confirm-gated nudge → roadmap slide.

## Stretch goals — ONLY if ahead of schedule (in this order)

1. RAG: move playbook into n8n vector store; note in doc why in-context was
   sufficient at this scale.
2. MCP: expose one mock tool via n8n's MCP server node; reference in design doc
   section 1(e) either way (describe mock layer as future MCP servers consumed by
   monitor agent, chat agent, and future HR/legal agents).
3. Extra chat tools; richer Slack formatting; simple dashboard page over /audit.

## Definition of done (core)

- `docker compose up` + import workflows + add API key = reproducible by a reviewer. ✓
- Design doc ≤2 pages covering architecture, LLM role, orchestration, trade-offs,
  security/governance, Workato mapping, MCP collaboration overview — written
  (`docs/solution-design.md`). ✓
- No secrets in the repo. ✓ (verified repeatedly against every workflow export)
- Demo shows: event trigger, stall detection, LLM-written human-readable summary,
  a retry surviving a 500, the schedule sweep catching all 3 customers
  autonomously, an idempotent autonomous nudge, a chat status answer +
  confirm-gated nudge, and a complete audit trail. **Remaining — Phase 6.**

## Working style for Claude Code

- Ask before adding scope; the cut order above is binding. Never let stretch goals
  precede a phase's completion.
- Prefer boring, readable Python. Log to stdout generously — the demo benefits.
- When Travis reports an n8n issue, request the exported workflow JSON or the node
  error text and debug from that.
