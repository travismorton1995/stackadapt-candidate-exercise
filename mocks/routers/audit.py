import logging
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

import db

logger = logging.getLogger("mocks.audit")
router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEntry(BaseModel):
    run_id: str
    trigger: str
    customer_id: str
    state_snapshot: Optional[Any] = None
    llm_verdict: Optional[Any] = None
    action_taken: str


@router.post("")
def post_audit(entry: AuditEntry):
    timestamp = db.insert_audit(
        entry.run_id,
        entry.trigger,
        entry.customer_id,
        entry.state_snapshot,
        entry.llm_verdict,
        entry.action_taken,
    )
    return {"ok": True, "timestamp": timestamp}


@router.get("")
def get_audit():
    logger.info("GET /audit")
    return db.list_audit()
