import logging

from fastapi import APIRouter

from fixtures_loader import FIXTURES_DIR, load_fixture

logger = logging.getLogger("mocks.salesforce")
router = APIRouter(prefix="/salesforce", tags=["salesforce"])


@router.get("/opportunities")
def list_opportunities():
    logger.info("GET /salesforce/opportunities (list)")
    customer_ids = sorted(p.stem.replace("_salesforce", "") for p in FIXTURES_DIR.glob("*_salesforce.json"))
    return {"customer_ids": customer_ids}


@router.get("/opportunities/{customer_id}")
def get_opportunity(customer_id: str):
    logger.info("GET /salesforce/opportunities/%s", customer_id)
    return load_fixture("salesforce", customer_id)
