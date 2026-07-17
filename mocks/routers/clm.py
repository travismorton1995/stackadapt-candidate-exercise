import logging

from fastapi import APIRouter

from fixtures_loader import load_fixture

logger = logging.getLogger("mocks.clm")
router = APIRouter(prefix="/clm", tags=["clm"])


@router.get("/contracts/{customer_id}")
def get_contract(customer_id: str):
    logger.info("GET /clm/contracts/%s", customer_id)
    return load_fixture("clm", customer_id)
