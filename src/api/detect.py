from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..detectors.registry import registry as detector_registry
from ..normalize.normalizer import normalize_text

router = APIRouter(prefix="/detect", tags=["detect"])


class DetectRequest(BaseModel):
    text: str = Field(..., max_length=200_000)
    domain: str = "global"
    locale: str = "ko-KR"
    io_type: str = Field("input", pattern="^(input|output|both)$")
    enabled_categories: Optional[List[str]] = None


class Match(BaseModel):
    detector_id: str
    category: str
    sub_category: str
    locale: str
    start: int
    end: int
    matched_text: str
    confidence: float
    rule_hint: Optional[str] = None


class DetectResponse(BaseModel):
    normalized_text: str
    matches: List[Match]
    risk_score: float
    categories: List[str]


@router.post("", response_model=DetectResponse)
def post_detect(req: DetectRequest) -> DetectResponse:
    norm = normalize_text(req.text)
    detectors = detector_registry.resolve(
        domain=req.domain,
        locale=req.locale,
        io_type=req.io_type,
        categories=req.enabled_categories,
    )
    matches: List[Match] = []
    cats: set[str] = set()
    risk = 0.0
    for det in detectors:
        for m in det.scan(norm):
            matches.append(Match(**m))
            cats.add(f"{m['category']}.{m['sub_category']}")
            # severity-weighted aggregation; floor so multiple low confs still ramp up.
            risk = max(risk, m["confidence"])
    return DetectResponse(
        normalized_text=norm,
        matches=matches,
        risk_score=round(risk, 4),
        categories=sorted(cats),
    )
