import logging
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("mocks.webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

N8N_WEBHOOK_BASE_URL = os.environ.get("N8N_WEBHOOK_BASE_URL", "http://n8n:5678/webhook")


class SimulateRequest(BaseModel):
    customer_id: str


@router.post("/simulate/{event}")
def simulate(event: str, body: SimulateRequest):
    url = f"{N8N_WEBHOOK_BASE_URL}/{event}"
    payload = {
        "event": event,
        "customer_id": body.customer_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response = httpx.post(url, json=payload, timeout=5.0)
        logger.info("forwarded event=%s to %s -> status=%s", event, url, response.status_code)
        return {"forwarded": True, "target_url": url, "n8n_status": response.status_code}
    except httpx.HTTPError as exc:
        logger.warning("failed to forward event=%s to %s: %s", event, url, exc)
        return {"forwarded": False, "target_url": url, "error": str(exc)}
