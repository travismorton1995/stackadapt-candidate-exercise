import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

import db

logger = logging.getLogger("mocks.slack")
router = APIRouter(prefix="/slack", tags=["slack"])


class NotifyRequest(BaseModel):
    channel: str
    text: str
    customer_id: Optional[str] = None


@router.post("/notify")
def post_notify(body: NotifyRequest):
    db.log_slack_message(body.channel, body.text)
    logger.info("[SLACK #%s] %s", body.channel, body.text)
    return {"ok": True, "customer_id": body.customer_id}


@router.get("/log")
def get_log():
    # Convenience endpoint for the demo -- not in the original spec, but "visible log" implies one.
    logger.info("GET /slack/log")
    return db.list_slack_log()
