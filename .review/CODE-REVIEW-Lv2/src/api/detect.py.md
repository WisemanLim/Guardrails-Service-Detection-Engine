# `src/api/detect.py` — File Review (Level 2)

## Pre-Review Header

- 역할: `POST /detect` 핵심 파이프라인. normalize → resolve → scan → aggregate.
- 진입점에서의 거리: 1
- 라인 수: 63
- 주요 export: `router`, `DetectRequest`, `Match`, `DetectResponse`, `post_detect`
- 의존 모듈 (internal): `..detectors.registry.registry`, `..normalize.normalizer.normalize_text`
- 사용된 외부 패키지: `fastapi`, `pydantic`
- 부수효과: 없음 (read-only registry 소비, pure compute).
- 동시성 모델: 동기 핸들러. 13개 regex `finditer` 직렬 실행.
- 테스트 커버리지 흔적: 6개 케이스에서 직접 호출 (`tests/test_detectors.py`).

---

## Source

```python path=src/api/detect.py lines=1-63
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
```

**분석 / Analysis (Level 2)**
- L1–4: stdlib `Optional/List` + Pydantic v2. Python 3.11+ 라 `list[str]` 도 가능하나 일관성을 위해 명시 typing 사용.
- L9: `prefix="/detect"` + L39 `@router.post("")` → 결국 `POST /detect`. 단수 URL이 동사스럽지만 REST 관용.
- L12–17: `DetectRequest`
  - `text`: `Field(..., max_length=200_000)` — Pydantic이 길이 초과 시 422.
  - `domain`, `locale`: 자유 문자열 default. **검증 없음** — 임의 문자열을 받아 registry.resolve로 흘려보냄. unknown domain은 silent로 0건 매치 → 호출자가 알아차리기 어려움.
  - `io_type`: `pattern="^(input|output|both)$"` 정규식 검증. `both` 도 허용 — registry resolve에서 `io_type not in d.io_types and "both" not in d.io_types` 분기에 매칭.
  - `enabled_categories: Optional[List[str]]` — 화이트리스트. 명시 안 함이 기본.
- L20–29: `Match` — `detector.scan()` 가 yield 하는 dict 키와 1:1. `rule_hint` 만 Optional. 다른 키 누락 시 `Match(**m)` 가 ValidationError → 500.
- L32–36: `DetectResponse` — `matches` 는 List[Match], `risk_score`/`categories` 집계 필드.
- L40: `def post_detect` 동기. detector 13개 × O(n) regex = CPU-bound. 200KB 입력 + 13개 정규식 = 약 2.6MB 패스 → uvloop 위에서 단일 worker 점유.
- L41: `norm = normalize_text(req.text)` — 한 번만 정규화. detector 마다 재정규화 안 함 ✓.
- L42–47: `detector_registry.resolve(...)` 키워드 인자 호출. `resolve`는 generator라 lazy iteration. 다만 L51의 `for det in detectors` 가 즉시 소비.
- L48–50: `matches`, `cats`(set), `risk(float)` 누산기 초기화. set은 카테고리 dedup.
- L51: outer loop — 도메인 필터 통과 detector.
- L52: `for m in det.scan(norm)` — generator 소비. `RegexDetector.scan`이 dict yield.
- L53: `Match(**m)` — **암묵 schema 계약**. detector 추가 시 dict 키를 정확히 맞춰야 함. 새 detector가 `rule_hint`를 빼면 OK이지만 `confidence` 누락 시 `ValidationError` → 500. 형식 강제 수단 부재.
- L54: `f"{m['category']}.{m['sub_category']}"` — `pii.email` 같은 합성 키. Match에 이미 두 필드 있어 중복이지만 응답 편의 위해 별도 set 유지.
- L55: 주석 "floor so multiple low confs still ramp up" 이 코드와 불일치. 실제 코드 `risk = max(risk, m["confidence"])` 는 그냥 최댓값이지 "floor + ramp up" 동작 아님. 주석이 의도, 코드는 단순 max — 둘 중 하나가 맞고 둘 중 하나는 거짓.
- L56: `risk = max(risk, m["confidence"])` — 최댓값. 매치 0건이면 0.0 유지.
- L57–62: `DetectResponse` 빌드. `round(risk, 4)` 소수 자릿수 정리. `sorted(cats)` 로 결정적 출력.

**짚어볼 점 / Watch-outs**
- **L55 주석/코드 불일치** — 위험 점수 정책이 모호. 명세상 "max" 인지 "ramp up" 인지 PRD 확인 후 정정 필요. 동일 카테고리 여러 매치가 약한 confidence(0.6 IPv4)만 잡혀도 risk_score=0.6 그대로. 누적/가중 합산 정책이 필요한지 product 결정 사항.
- **detector dict 스키마 암묵 계약** — `base.py` docstring 외 강제 수단 없음. `TypedDict` 도입 권장.
- **unknown domain/locale silent**: `domain="manufacturing-food"` 인데 P1 단독 배포 상태면 0건 매치. 호출자 입장에선 "안전" 응답으로 오해. registry.resolve가 0건일 때 422 또는 경고 필드 추가 권장.
- **`enabled_categories`** 가 `registry.py:41`의 `d.category not in categories` 와 매칭. category는 `pii` / `credentials` 같은 상위. sub_category 화이트리스트는 미지원. 명세 OK라면 문서화 필요.
- 매치 수가 많은 악성 입력(예: 1000개 카드 번호 매치)에서 응답 크기 폭증. 응답에 `len(matches)` cap 정책 없음.
- `Match(**m)` 가 매 매치마다 Pydantic 검증을 돌림 — 1000 매치 = 1000번 validation. 핫패스 비용 측정 권장.

---

## File-level Verdict

- **강점**
  1. 파이프라인이 6단계로 깔끔: normalize → resolve → scan → set → max → respond.
  2. Pydantic v2 입력·출력 모델로 OpenAPI 자동 생성 친화.
  3. `enabled_categories` 옵션으로 호출자가 카테고리 화이트리스트 가능.
- **위험**
  1. 위험점수 주석과 코드 불일치 (`max` vs `ramp up`) — 정책 모호.
  2. detector dict 스키마 비형식적 → 회귀 위험.
  3. unknown domain/locale 가 silent 0건 매치 → 호출자 오해 가능.
- **개선 권고**
  1. risk 집계 정책 명문화 + 함수 추출 (`_aggregate_risk(matches) -> float`) + 단위 테스트.
  2. detector match를 `TypedDict` 또는 `@dataclass` 로 형식화하고 `RegexDetector.scan` 반환 타입 강제.
  3. `domain`/`locale` allowlist 검증 (`enum` 또는 settings 기반) 후 422 응답.
- **재읽기 권고 레벨**: **중**. 핵심 파이프라인이라 정책 변경 시 가장 먼저 봐야 함.
