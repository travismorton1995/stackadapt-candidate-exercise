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
  Two workflows: (1) Monitor (autonomous loop), (2) Chat (agent with tools).
- **FastAPI mock server** (container, localhost:8000) — fake Salesforce / CLM /
  NetSuite / provisioning APIs backed by JSON fixtures, plus an /audit endpoint
  backed by SQLite, plus one deliberately flaky endpoint to demo retries.
- **LLM API** (external) — Gemini via Google AI Studio free tier, or Anthropic API.
  Called by n8n's AI Agent / LLM nodes. NEVER commit API keys. Use .env +
  .gitignore from the first commit; provide .env.example.

Key design principle (state it in the doc): **the LLM recommends, code decides.**
The LLM returns a structured JSON verdict; a deterministic n8n IF/Switch branch
routes to notify vs. act, constrained by an action allowlist.

Playbook grounding: 3 short markdown policy docs injected directly into the
assessment prompt (no vector store in core scope — see stretch goals).

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

- `GET /salesforce/opportunities/{customer_id}` → { customer_id, opportunity_stage,
  close_date, account_owner, contact_email, product_tier }
- `GET /clm/contracts/{customer_id}` → { customer_id, status
  (draft|sent|signed), signed_date, contract_value }
- `GET /netsuite/invoices/{customer_id}` → { customer_id, invoice_status
  (not_created|issued|paid), issued_date, paid_date, amount }
  **This endpoint is the flaky one: ~30% of calls return HTTP 500** (configurable
  via env var FLAKY_RATE; set to 0 for tests, mention in README).
- `GET /provisioning/status/{customer_id}` → { customer_id, steps: [ { name,
  owner (cs|customer), status (pending|in_progress|done), due_date } ] }
- `POST /provisioning/nudge` → { customer_id, message } → simulates sending a
  templated reminder to the customer contact; returns { sent: true, nudge_id }.
  Must be **idempotent per (customer_id, day)** — repeat calls same day return the
  existing nudge_id with sent: false, "already_nudged". This is a talking point.
- `POST /slack/notify` → { channel, text } → mock Slack; appends to a visible log.
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
- **globex** — the healthy customer. Everything on track, provisioning 60% done,
  nothing overdue. → LOW risk. Expected: log only, no notification. (Shows the
  agent doesn't cry wolf.)
- **initech** — the edge case. Invoice issued but unpaid past playbook threshold;
  provisioning blocked on a CS-owned step. → MEDIUM risk. Expected: notification,
  NO autonomous action (action is CS-owned, not on the allowlist).

## Playbook docs (markdown, injected into the prompt)

1. `invoicing-policy.md` — invoices issued within 5 business days of signature;
   payment expected within 15 days of issue.
2. `provisioning-checklist.md` — standard steps per product tier, expected
   durations, which steps are customer-owned vs CS-owned.
3. `escalation-policy.md` — what counts as low/medium/high risk; allowlisted
   autonomous actions (send templated nudge for overdue CUSTOMER-owned steps only;
   create follow-up task); everything else notifies humans.

## LLM assessment prompt (Monitor workflow)

Input: merged customer state JSON + full text of the 3 playbook docs.
Output: STRICT JSON only:

```json
{
  "risk_level": "low|medium|high",
  "risks": ["..."],
  "summary": "2-3 sentence human-readable status for the CS team",
  "recommended_action": "none|notify|nudge_customer|create_task",
  "reasoning": "1-2 sentences citing the playbook rule involved"
}
```

Instruct the model to cite which playbook rule triggered each risk. The n8n branch
reads risk_level + recommended_action; only allowlisted actions execute.

## n8n workflows (built manually on canvas — provide guidance when asked)

**Workflow 1 — Monitor:**
Schedule Trigger (every 2 min for demo) AND Webhook Trigger (from
/webhooks/simulate) → fetch customer list → loop → 4 parallel HTTP Request nodes
(retry 3x, backoff) → Merge into state object → LLM node with assessment prompt →
Parse/validate JSON → Switch on risk_level/recommended_action → branches:
(a) POST /slack/notify, (b) POST /provisioning/nudge, (c) no-op → ALL paths end in
POST /audit. Attach an Error Workflow that logs failures to /audit and notifies.

**Workflow 2 — Chat:**
n8n Chat Trigger (hosted chat UI) → AI Agent node with 2 tools:
`get_customer_state` (calls the 4 GET endpoints) and `draft_nudge` (drafts, shows
to user, POSTs /provisioning/nudge on confirmation). System prompt includes the
playbook docs. Log agent actions to /audit.

## Build order (thin slice first — protect against running out of time)

- **Phase 0 (~1–1.5h):** docker-compose with n8n + mocks skeleton; verify n8n can
  reach http://mocks:8000; .env/.gitignore/.env.example; git init + GitHub private repo.
- **Phase 1 (~2h):** mocks with ONE customer (acme) + /slack/notify + /audit.
  No flakiness yet.
- **Phase 2 (~2–3h):** THIN SLICE — Monitor workflow end-to-end for acme:
  trigger → state → LLM → notification → audit. Milestone: "working prototype exists."
- **Phase 3 (~2–3h):** add globex + initech fixtures; add Switch branching + nudge
  action + idempotency; enable flaky endpoint + retries + error workflow.
- **Phase 4 (~1.5–2h):** Chat workflow, minimal 2-tool version.
- **Phase 5 (~2h):** design doc (draft from this file's "Why" + architecture
  sections), README with run instructions, export workflows to /workflows.
- **Phase 6 (~1–1.5h):** demo recording: problem → simulate contract_signed webhook →
  agent catches acme stall → show Slack log + audit trail → show retry surviving a
  500 → chat status query → roadmap slide.

## Stretch goals — ONLY if ahead of schedule (in this order)

1. RAG: move playbook into n8n vector store; note in doc why in-context was
   sufficient at this scale.
2. MCP: expose one mock tool via n8n's MCP server node; reference in design doc
   section 1(e) either way (describe mock layer as future MCP servers consumed by
   monitor agent, chat agent, and future HR/legal agents).
3. Extra chat tools; richer Slack formatting; simple dashboard page over /audit.

## Definition of done (core)

- `docker compose up` + import workflows + add API key = reproducible by a reviewer.
- Demo shows: event trigger, stall detection, LLM-written human-readable summary,
  a retry surviving a 500, an idempotent autonomous nudge, a chat status answer,
  and a complete audit trail.
- Design doc ≤2 pages covering architecture, LLM role, orchestration, trade-offs,
  security/governance, Workato mapping, MCP collaboration overview.
- No secrets in the repo.

## Working style for Claude Code

- Ask before adding scope; the cut order above is binding. Never let stretch goals
  precede a phase's completion.
- Prefer boring, readable Python. Log to stdout generously — the demo benefits.
- When Travis reports an n8n issue, request the exported workflow JSON or the node
  error text and debug from that.
