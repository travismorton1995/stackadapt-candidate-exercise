# CS Onboarding Agent — StackAdapt Candidate Exercise

Solution design and prototype for the "Enterprise Agent Solutions Developer"
candidate exercise (Travis Morton). See [CLAUDE.md](CLAUDE.md) for the full
build brief and [docs/solution-design.md](docs/solution-design.md) for the
design doc (added in a later phase).

## What this is

An AI agent that monitors client onboarding across a mocked SaaS stack
(Salesforce CRM → CLM → NetSuite ERP → SaaS provisioning), detects risks and
stalls, notifies the CS team via Slack, and takes a narrow set of safe
autonomous actions (idempotent customer nudges). It also exposes a chat
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
     500, used to demo retry handling. Default `0.3`. Set to `0` to disable.

2. Start the stack:
   ```
   docker compose up -d --build
   ```

3. Verify the mock API is up: http://localhost:8000/health should return
   `{"status": "ok"}`. Interactive API docs: http://localhost:8000/docs

4. Open the n8n canvas at http://localhost:5678 and create a local owner
   account (first run only). Import workflows from `/workflows` if provided,
   or build them following the guidance in CLAUDE.md.

## Mock API

All endpoints are documented interactively at http://localhost:8000/docs.
Summary:

| Endpoint | Purpose |
|---|---|
| `GET /salesforce/opportunities/{customer_id}` | Opportunity/account info |
| `GET /clm/contracts/{customer_id}` | Contract status & signature date |
| `GET /netsuite/invoices/{customer_id}` | Invoice status (flaky, see `FLAKY_RATE`) |
| `GET /provisioning/status/{customer_id}` | Onboarding checklist steps |
| `POST /provisioning/nudge` | Send a templated customer reminder (idempotent per customer per day) |
| `POST /slack/notify` | Mock Slack post |
| `GET /slack/log` | View what's been "posted" to mock Slack (demo convenience, not in original spec) |
| `POST /audit` / `GET /audit` | Write/read the audit trail (SQLite-backed) |
| `POST /webhooks/simulate/{event}` | Fire a webhook at n8n on demand (`contract_signed`, `invoice_paid`) — forwards to `N8N_WEBHOOK_BASE_URL/{event}` |

Customer IDs currently available: `acme` (stalled/high-risk fixture). More
customers (`globex`, `initech`) are added in a later build phase.

## Playbook

Three markdown policy docs in `/playbook` are injected into the LLM's
assessment prompt: `invoicing-policy.md`, `provisioning-checklist.md`,
`escalation-policy.md`. These are the ground truth the agent reasons against —
edit them to change agent behavior without touching code.

## Repo layout

```
/mocks            FastAPI app (main.py, routers per system, db.py, fixtures/*.json)
/playbook         3 markdown policy docs injected into the LLM prompt
/workflows        exported n8n workflow JSON (exported manually from the canvas)
/docs             solution-design.md
docker-compose.yml
.env.example
```

## Development notes

- The `mocks` service bind-mounts `./mocks:/app` with `uvicorn --reload`, so
  Python code edits take effect without a rebuild. Changes to
  `requirements.txt` do need `docker compose up -d --build mocks`.
- The audit trail and nudge idempotency lock both live in `mocks/audit.db`
  (SQLite, gitignored, recreated automatically on first request).
