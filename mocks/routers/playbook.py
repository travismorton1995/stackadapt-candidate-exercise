import logging
from pathlib import Path

from fastapi import APIRouter

logger = logging.getLogger("mocks.playbook")
router = APIRouter(prefix="/playbook", tags=["playbook"])

PLAYBOOK_DIR = Path(__file__).parent.parent / "playbook"
DOC_ORDER = ["invoicing-policy.md", "provisioning-checklist.md", "escalation-policy.md"]


@router.get("")
def get_playbook():
    logger.info("GET /playbook")
    sections = []
    for filename in DOC_ORDER:
        text = (PLAYBOOK_DIR / filename).read_text()
        sections.append(f"## {filename}\n\n{text}")
    return {"text": "\n\n".join(sections)}
