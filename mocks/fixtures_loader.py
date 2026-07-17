import json
import logging
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger("mocks.fixtures")

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(system: str, customer_id: str) -> dict:
    path = FIXTURES_DIR / f"{customer_id}_{system}.json"
    if not path.exists():
        logger.warning("fixture not found: system=%s customer_id=%s", system, customer_id)
        raise HTTPException(status_code=404, detail=f"No {system} data for customer_id '{customer_id}'")
    with open(path) as f:
        return json.load(f)
