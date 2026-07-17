import logging

from fastapi import FastAPI

import db
from routers import audit, clm, netsuite, provisioning, salesforce, slack, webhooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mocks")

app = FastAPI(title="CS Onboarding Agent Mocks")

app.include_router(salesforce.router)
app.include_router(clm.router)
app.include_router(netsuite.router)
app.include_router(provisioning.router)
app.include_router(slack.router)
app.include_router(audit.router)
app.include_router(webhooks.router)


@app.on_event("startup")
def on_startup():
    db.init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
