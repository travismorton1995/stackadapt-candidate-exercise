import logging

from fastapi import APIRouter

from fixtures_loader import load_fixture

logger = logging.getLogger("mocks.salesforce")
router = APIRouter(prefix="/salesforce", tags=["salesforce"])


@router.get("/opportunities/{customer_id}")
def get_opportunity(customer_id: str):
    logger.info("GET /salesforce/opportunities/%s", customer_id)
    return load_fixture("salesforce", customer_id)
