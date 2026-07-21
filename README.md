# CS Onboarding Agent — StackAdapt Candidate Exercise

Solution design and prototype for the "Enterprise Agent Solutions Developer"
candidate exercise (Travis Morton). See [CLAUDE.md](CLAUDE.md) for the full
build brief and [docs/solution-design.md](docs/solution-design.md) for the
design doc.

## What this is

An AI agent that monitors client onboarding across a mocked SaaS stack
(Salesforce CRM → CLM → NetSuite ERP → SaaS provisioning), detects risks and
stalls, notifies the CS team via Slack, and takes a narrow set of safe
autonomous actions (idempotent customer nudges). It operates both
autonomously (event-driven + a twice-daily schedule sweep) and via a chat
interface for CS users. Orchestration is built in n8n; the mock systems are a
real FastAPI app.

## Prerequisites

- Docker Desktop (with WSL2 backend on Windows)
- An Anthropic API key (https://console.anthropic.com/settings/keys)

## Setup

1. Copy the env template and fill in your values:
   ```
   cp .env.example .env
   ```
   - `ANTHROPIC_API_KEY` — your Anthropic API key (used by n8n's Anthropic
     Chat Model node, configured on the canvas, not read directly from this
     file by n8n itself — you'll paste it into an n8n credential instead).
   - `N8N_ENCRYPTION_KEY` — any random string (e.g. `openssl rand -hex 32`).
     n8n uses this to encrypt saved credentials. Keep it stable once set.
   - `FLAKY_RATE` — fraction of `/netsuite/invoices` calls that return HTTP
     500, used to demo retry handling. Default `0.2`. Set to `0` to disable.

2. Start the stack:
   ```
   docker compose up -d --build
   ```

3. Verify the mock API is up: http://localhost:8000/health should return
   `{"status": "ok"}`. Interactive API docs: http://localhost:8000/docs

4. Open the n8n canvas at http://localhost:5678, create a local owner account
   (first run only), and import the three workflows from `/workflows`:
   `Monitor.json`, `Chat.json`, `Error Handler.json`.
   - Each workflow using the LLM needs an Anthropic credential created once in
     n8n's UI (not read from `.env`).
   - `Monitor`'s and `Chat`'s workflow Settings need **Error Workflow** set to
     `Error Handler`.
   - Once `Monitor` is activated, its Schedule Trigger will fire on its own
     twice a day (`0 7,15 * * *` — see `GENERIC_TIMEZONE` in `.env`) and sweep
     every customer, in addition to reacting to simulated webhook events.

## Mock API

All endpoints are documented interactively at http://localhost:8000/docs.
Summary:

| Endpoint | Purpose |
|---|---|
| `GET /salesforce/opportunities` | List all customer_ids with an opportunity (drives Monitor's schedule sweep) |
| `GET /salesforce/opportunities/{customer_id}` | Opportunity/account info |
| `GET /clm/contracts/{customer_id}` | Contract status & signature date |
| `GET /netsuite/invoices/{customer_id}` | Invoice status (flaky, see `FLAKY_RATE`) |
| `GET /provisioning/status/{customer_id}` | Onboarding checklist steps |
| `POST /provisioning/nudge` | Send a templated customer reminder (idempotent per customer per day) |
| `POST /slack/notify` | Mock Slack post |
| `GET /slack/log` | View what's been "posted" to mock Slack (demo convenience, not in original spec) |
| `GET /playbook` | Concatenated text of the 3 policy docs (for LLM narration) |
| `GET /playbook/rules` | Structured thresholds (`playbook/rules.json`) the deterministic classifier reads |
| `POST /audit` / `GET /audit` | Write/read the audit trail (SQLite-backed) |
| `POST /webhooks/simulate/{event}` | Fire a webhook at n8n on demand (`contract_signed`, `invoice_paid`) — forwards to `N8N_WEBHOOK_BASE_URL/{event}` |

Customer IDs: `acme` (stalled, HIGH risk), `globex` (healthy, LOW risk),
`initech` (edge case — payment breach + CS-owned bottleneck, MEDIUM risk, no
autonomous action).

## Playbook

Three markdown policy docs in `/playbook` (`invoicing-policy.md`,
`provisioning-checklist.md`, `escalation-policy.md`) are the human-readable
ground truth, injected into the LLM's narration prompt. The actual
classification decision is deterministic: `playbook/rules.json` holds the
same policy as structured thresholds a Code node (`Classify`, in the Monitor
workflow) evaluates directly — editing thresholds there changes agent
behavior without touching workflow logic. See the design doc for why
classification is code-driven rather than LLM-driven.

## Workflows

- **Monitor** — autonomous. Webhook (event-driven) + Schedule Trigger (cron)
  → fetch state → deterministic `Classify` → conditional LLM narration →
  notify/nudge decision → audit.
- **Chat** — conversational. Hosted chat UI → AI Agent (Claude Sonnet 5) with
  two tools: `get_customer_state` (read-only lookup) and `draft_nudge`
  (preview-then-confirm autonomous action).
- **Error Handler** — catches uncaught failures from the other two, logs to
  `/audit`, posts to `#ops-alerts`.

## Repo layout

```
/mocks            FastAPI app (main.py, routers per system, db.py, fixtures/*.json)
/playbook          3 markdown policy docs + rules.json (structured thresholds)
/workflows        Exported n8n workflow JSON (Monitor, Chat, Error Handler)
/docs             solution-design.md
docker-compose.yml
.env.example
```

## Development notes

- The `mocks` service bind-mounts `./mocks:/app` with `uvicorn --reload`, so
  Python code edits take effect without a rebuild. Changes to
  `requirements.txt` do need `docker compose up -d --build mocks`.
- The audit trail and nudge idempotency lock both live in `mocks/audit.db`
  (SQLite, gitignored, recreated automatically on first request). Reset it
  with `docker compose stop mocks && rm -f mocks/audit.db && docker compose up -d mocks`.
