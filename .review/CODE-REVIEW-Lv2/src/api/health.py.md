# `src/api/health.py` — File Review (Level 2)

## Pre-Review Header

- 역할: `GET /health` 핸들러. liveness/readiness + detector 카탈로그 노출.
- 진입점에서의 거리: 1 (main.py가 라우터 마운트)
- 라인 수: 17
- 주요 export: `router: APIRouter`
- 의존 모듈 (internal): `..config.settings`, `..detectors.registry.registry`
- 사용된 외부 패키지: `fastapi.APIRouter`
- 부수효과: 없음 (read-only).
- 동시성 모델: 동기 핸들러. registry는 read-only 리스트 노출이라 race 없음.
- 테스트 커버리지 흔적: `tests/test_detectors.py::test_health_lists_detectors` (status_code, "pii.id.rrn.kr" 포함 검사).

---

## Source

```python path=src/api/health.py lines=1-17
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
```

**분석 / Analysis (Level 2)**
- L1: `APIRouter` — FastAPI 라우터 단위. prefix가 없으므로 `/health` 그대로 노출.
- L3–4: 설정/레지스트리 양쪽을 직접 read. dependency injection 미사용 — 작은 규모라 무해.
- L6: `router = APIRouter()` 모듈 전역. import 시 1회 생성, 이후 main.py가 `include_router(health.router)`.
- L9: `@router.get("/health")` — HEAD 자동 추가 (FastAPI 기본). Kubernetes liveness/readiness probe에서 GET 사용에 적합.
- L10: 반환 타입 `-> dict` 만 명시. `response_model` 미지정이라 응답 모델 검증·OpenAPI 스키마 약함. 자유 dict 반환은 prototype 단계에서 OK.
- L12–15: 단순 dict literal 반환. `settings.enabled_domains` 는 list 참조 반환 — **흔한 실수**: 호출자가 응답 dict를 mutate 해 list 에 push하면 frozen dataclass 안의 list까지 영향. 단, FastAPI 응답 직렬화는 deepcopy 없이 그대로 orjson.dumps 하지만 응답 후 객체 변경은 클라이언트가 못 함. 내부에서 같은 list를 다른 endpoint와 공유하므로 `list(settings.enabled_domains)` 처럼 방어 복사 권장.
- L15: `detector_registry.list_ids()` — 매 호출 새 list 반환 (`registry.py:23`), share aliasing 없음.

**짚어볼 점 / Watch-outs**
- detector id 카탈로그가 prod에서도 노출됨. 공격자에게 어떤 PII가 탐지되는지 알려주는 정보. Phase별 토글(예: `GUARDRAILS_HEALTH_VERBOSE=0`) 권장.
- liveness vs readiness 구분 없음. detector registry 가 비어 있어도(예: `GUARDRAILS_ENABLED_DOMAINS=""`) status="ok" 반환. readiness 의미를 강화하려면 `len(detectors)==0`에서 503 권장.
- `response_model` 미지정 — OpenAPI 문서가 빈약. operator/SDK 자동 생성 친화성 낮음.
- 응답 dict 가 매 호출 새로 빌드 — cache 효과 없음. 부팅 후 불변이라 LRU 1개로 충분.

---

## File-level Verdict

- **강점**
  1. 17 LOC, 의도가 1초 안에 파악됨.
  2. detector id 노출로 디버깅·운영 가시성 양호.
  3. read-only 동기 핸들러라 부하 거의 없음.
- **위험**
  1. detector 카탈로그 노출이 보안 정보 누설 — prod 토글 부재.
  2. detector 0건이어도 status=ok 반환 → false-positive healthy.
  3. `response_model` 미지정 → 스키마 drift 가능.
- **개선 권고**
  1. `class HealthResponse(BaseModel)` 정의 + `response_model=HealthResponse` 지정.
  2. detector 개수/필수 도메인 누락 시 503 반환하는 readiness 분기 또는 별도 `/ready` 신설.
  3. ENV로 카탈로그 노출 토글, 또는 `/health/detectors` 별도 endpoint로 분리.
- **재읽기 권고 레벨**: **낮음**.
