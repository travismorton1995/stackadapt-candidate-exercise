import logging
import os
import random

from fastapi import APIRouter, HTTPException

from fixtures_loader import load_fixture

logger = logging.getLogger("mocks.netsuite")
router = APIRouter(prefix="/netsuite", tags=["netsuite"])


@router.get("/invoices/{customer_id}")
def get_invoice(customer_id: str):
    flaky_rate = float(os.environ.get("FLAKY_RATE", "0"))
    if random.random() < flaky_rate:
        logger.warning("GET /netsuite/invoices/%s simulated 500 (FLAKY_RATE=%s)", customer_id, flaky_rate)
        raise HTTPException(status_code=500, detail="NetSuite is temporarily unavailable")

    logger.info("GET /netsuite/invoices/%s", customer_id)
    return load_fixture("netsuite", customer_id)
