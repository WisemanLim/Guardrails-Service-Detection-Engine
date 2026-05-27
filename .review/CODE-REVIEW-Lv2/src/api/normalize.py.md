# `src/api/normalize.py` — File Review (Level 2)

## Pre-Review Header

- 역할: `POST /normalize` 핸들러. 입력 텍스트 정규화 + 숫자만 추출.
- 진입점에서의 거리: 1
- 라인 수: 24
- 주요 export: `router`, `NormalizeRequest`, `NormalizeResponse`, `post_normalize`
- 의존 모듈 (internal): `..normalize.normalizer.normalize_text`
- 사용된 외부 패키지: `fastapi`, `pydantic`
- 부수효과: 없음 (pure compute).
- 동시성 모델: 동기 핸들러.
- 테스트 커버리지 흔적: `tests/test_detectors.py::test_normalize_endpoint_strips_fullwidth`.

---

## Source

```python path=src/api/normalize.py lines=1-24
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
```

**분석 / Analysis (Level 2)**
- L6: `APIRouter(prefix="/normalize", tags=["normalize"])` — POST `""` 가 결과적으로 `POST /normalize` 가 됨. trailing slash 없음 (FastAPI redirect_slashes 기본값 True).
- L9–11: `Field(..., max_length=200_000)` — `...` 은 Ellipsis 로 "required". `max_length` 는 character 단위 (Pydantic v2). 200KB 가 character 가 아닌 byte 라면 UTF-8 다바이트 문자에서 실제 byte 크기는 더 큼. 입력 DoS 보호로는 1차선 OK.
- L10: `locale: str = "ko-KR"` — 입력 받지만 `post_normalize` 가 사용 안 함. dead field. 향후 locale별 정규화 분기 위해 남긴 placeholder로 보임.
- L14–16: 응답 모델 2필드. orjson 직렬화 호환 OK.
- L19: `@router.post("", response_model=NormalizeResponse)` — `response_model` 명시는 OpenAPI 스키마 + 응답 검증 모두 작동.
- L21: `norm = normalize_text(req.text)` — `req.text`는 Pydantic이 max_length 검증 후 통과한 문자열.
- L22: `digits = "".join(ch for ch in norm if ch.isdigit())` — generator → join. **`str.isdigit()` 가 Unicode "digit" 포괄**이라 ⓐ아라비아 숫자뿐 아니라 ② ③ ① 같은 circled digit 도 True. NFKC 정규화 후엔 대부분 ASCII 디지터로 통일되지만, 만약 `Ⅻ` (로마 숫자 12) 같은 케이스가 NFKC로 풀리지 않으면 `isdigit()` 가 False (그건 `isnumeric()` 영역). 카드/RRN 검증에 쓰이는 보조 view 이지만 이 endpoint 결과는 디버깅용. 호출자가 이걸 Luhn 입력으로 쓰면 NFKC만으로 모든 케이스가 ASCII가 되는지 신뢰 가능한지 검증 필요.
- L23: 반환 — Pydantic v2가 dict로 직렬화, ORJSONResponse가 bytes 응답.

**짚어볼 점 / Watch-outs**
- `locale` 필드 미사용 — 향후 locale별 정규화 룰 도입 전까지 API 사용자가 잘못 신뢰 가능 (예: `ja-JP` 보내면 다르게 처리될 거라 기대).
- `digits_only_view` 는 표시 목적인데 응답에 포함되면 PII 일부(전화번호의 숫자열)가 평문 노출되는 셈. detect endpoint와 동일한 누출 리스크 — redaction 정책 합의 필요.
- 200_000 char 입력은 `unicodedata.normalize` + 단일 패스 join 2회로 처리 — CPU 동기 호출이라 이벤트 루프 점유. async + offload 고려 가능하나 현 규모엔 과한 최적화.

---

## File-level Verdict

- **강점**
  1. 24 LOC로 의도가 단순·명확. `response_model` 지정으로 스키마 정합.
  2. `max_length=200_000` 입력 DoS 1차 방어.
  3. detect endpoint와 동일한 normalize 함수 공유 — 단일 진실원.
- **위험**
  1. `locale` 미사용 dead 입력 — API 계약 혼란.
  2. `digits_only_view` 응답 노출이 PII 평문 일부 누출.
  3. 200KB 동기 처리가 이벤트 루프 블로킹 가능.
- **개선 권고**
  1. `locale` 사용하든 제거. 사용 안 할 거면 응답에 `locale_echo` 정도로 정직하게 표시.
  2. `digits_only_view` 를 옵션 쿼리 플래그로 강등 (`include_digits=true` 명시 시만 반환).
  3. 200KB 한도 vs 시간 측정 — `time.perf_counter()` 로 한 번 측정 후 SLA 확정.
- **재읽기 권고 레벨**: **낮음**.
