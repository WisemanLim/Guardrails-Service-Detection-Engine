from fastapi import APIRouter

from ..config import settings
from ..detectors.registry import registry as detector_registry

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "domains": settings.enabled_domains,
        "locales": settings.enabled_locales,
        "detectors": detector_registry.list_ids(),
    }
