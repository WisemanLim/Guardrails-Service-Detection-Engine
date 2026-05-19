from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..normalize.normalizer import normalize_text

router = APIRouter(prefix="/normalize", tags=["normalize"])


class NormalizeRequest(BaseModel):
    text: str = Field(..., max_length=200_000)
    locale: str = "ko-KR"


class NormalizeResponse(BaseModel):
    normalized_text: str
    digits_only_view: str


@router.post("", response_model=NormalizeResponse)
def post_normalize(req: NormalizeRequest) -> NormalizeResponse:
    norm = normalize_text(req.text)
    digits = "".join(ch for ch in norm if ch.isdigit())
    return NormalizeResponse(normalized_text=norm, digits_only_view=digits)
