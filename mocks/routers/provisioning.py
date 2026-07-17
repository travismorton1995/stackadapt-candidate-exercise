import logging

from fastapi import APIRouter
from pydantic import BaseModel

import db
from fixtures_loader import load_fixture

logger = logging.getLogger("mocks.provisioning")
router = APIRouter(prefix="/provisioning", tags=["provisioning"])


class NudgeRequest(BaseModel):
    customer_id: str
    message: str


@router.get("/status/{customer_id}")
def get_status(customer_id: str):
    logger.info("GET /provisioning/status/%s", customer_id)
    return load_fixture("provisioning", customer_id)


@router.post("/nudge")
def post_nudge(body: NudgeRequest):
    nudge_id, is_new = db.get_or_create_nudge(body.customer_id, body.message)
    if is_new:
        logger.info("nudge sent to customer_id=%s nudge_id=%s", body.customer_id, nudge_id)
        return {"sent": True, "nudge_id": nudge_id}

    logger.info("nudge skipped (already sent today) customer_id=%s nudge_id=%s", body.customer_id, nudge_id)
    return {"sent": False, "nudge_id": nudge_id, "reason": "already_nudged"}
