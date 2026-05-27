# `src/main.py` — File Review (Level 2)

## Pre-Review Header

- 역할: FastAPI 앱 팩토리. uvicorn ASGI 타겟 노출(`app`). 부팅 시 detector 일괄 등록.
- 진입점에서의 거리: 0 (uvicorn 직접 import 타겟)
- 라인 수: 23 (<600 → block-mode 불필요)
- 주요 export: `create_app() -> FastAPI`, `app: FastAPI`
- 의존 모듈 (internal): `.api.detect`, `.api.health`, `.api.normalize`, `.config`, `.detectors.registry`, `.detectors.bootstrap`
- 사용된 외부 패키지: `fastapi`, `fastapi.responses.ORJSONResponse`
- 부수효과: 모듈 import 시 `app = create_app()` 실행 → detector registry 가 13건으로 채워짐. (전역 변이)
- 동시성 모델: 동기 함수. FastAPI app 자체는 ASGI 비동기 런타임 위. 부팅은 단일 스레드에서 직렬 실행.
- 테스트 커버리지 흔적: `tests/test_detectors.py:3` 에서 `from src.main import app` 으로 사용 — import 자체가 부트스트랩을 트리거.

---

## Source

```python path=src/main.py lines=1-23
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from .api import detect, health, normalize
from .config import settings
from .detectors.registry import registry as detector_registry
from .detectors.bootstrap import bootstrap_builtins


def create_app() -> FastAPI:
    app = FastAPI(
        title="Guardrails Detection Engine",
        version="0.1.0",
        default_response_class=ORJSONResponse,
    )
    bootstrap_builtins(detector_registry, enabled_domains=settings.enabled_domains)
    app.include_router(health.router)
    app.include_router(normalize.router)
    app.include_router(detect.router)
    return app


app = create_app()
```

**분석 / Analysis (Level 2)**
- L1–2: FastAPI 코어 + `ORJSONResponse` import. orjson은 dict/list 직렬화 시 stdlib json 대비 2~5배 빠르고 `datetime`·`UUID` native 지원. 응답 모델이 단순 dict라 효과 큼.
- L4: `.api import detect, health, normalize` — submodule import (각 모듈에 `router` 속성이 있어야 함). 이 시점에 `api/*.py` 의 모듈 레벨 코드(BaseModel 클래스 정의 등)가 실행됨. Pydantic v2는 클래스 정의 시점에 core schema를 컴파일하므로 콜드 스타트에 ms 단위 비용 추가.
- L5: `from .config import settings` — `config.py` 모듈 import 시점에 `os.getenv` 호출. ENV 변경은 이 import 후 무시됨 (frozen dataclass).
- L6: `registry`를 모듈 전역 싱글톤으로 import 후 alias. **흔한 실수**: 테스트에서 별도 app 인스턴스를 만들고 registry를 재초기화하려 할 때, 동일한 모듈 객체를 공유하므로 직렬 테스트 간 detector 누적 가능. 현재 코드는 `create_app()` 안에서 `register`만 호출하므로 두 번 호출하면 중복 등록 → `list_ids()`에 중복 id 등장.
- L10: `def create_app() -> FastAPI` — 팩토리 패턴은 테스트 격리에 권장되지만 L23의 `app = create_app()` 가 모듈 임포트만으로 부팅 부수효과를 일으킴. uvicorn은 `src.main:app`을 import할 때 이 라인을 실행해 detector 13건 등록.
- L11–15: FastAPI 생성자. `default_response_class=ORJSONResponse`는 라우터별 별도 지정 없이도 전 응답 적용 (FastAPI 0.95+ 정식 지원).
- L16: `bootstrap_builtins(detector_registry, enabled_domains=settings.enabled_domains)` — 키워드 인자 강제(`*` 컨벤션은 `bootstrap.py` 쪽). **유의**: `settings.enabled_domains` 는 `field(default_factory=lambda: _csv(...))` 로 인스턴스마다 다른 list 객체. import-time 1회 캡처되므로 ENV 변경은 재부팅까지 반영 안 됨.
- L17–19: router 마운트 순서가 OpenAPI 문서 순서에 그대로 반영. health → normalize → detect 가 합리적.
- L23: 전역 `app`. **부수효과 import**는 12-Factor 관점에서 호불호 갈리는 패턴. uvicorn 타겟으로 강제되는 부분이지만 단위 테스트에서 `from src.main import app` 자체가 부팅을 실행 → ENV mock이 import 전에 끝나야 함.

**짚어볼 점 / Watch-outs**
- `create_app()`이 호출될 때마다 *전역* `detector_registry`에 register가 누적된다. 테스트 격리 위해 factory 안에서 fresh registry를 만들어 inject 하는 구조가 더 안전.
- `bootstrap_builtins` 의 `enabled_domains` 가 빈 리스트(예: `GUARDRAILS_ENABLED_DOMAINS=""`)면 어떤 detector도 등록되지 않아 `/detect`가 항상 matches=[] 반환. `/health` 응답으로만 사후 진단 가능 — 부팅 로그 미발생 (logger 호출 없음).
- 미들웨어(CORS, Auth, Trusted-Host) 부재 — Docker `EXPOSE 8081` 이 외부 노출 시 PII 입력을 누구나 전송 가능.

---

## File-level Verdict

- **강점**
  1. 23 LOC로 명료한 부팅 시퀀스. 라우터·설정·detector 등록이 한눈에 들어옴.
  2. ORJSONResponse 기본화로 응답 성능 마이크로 최적화 적용.
  3. 팩토리 함수가 분리되어 차후 테스트용 fresh-app 주입 리팩터링 여지를 남김.
- **위험**
  1. 모듈 import 부수효과(`app = create_app()` + 전역 registry 누적) — 테스트 격리·재시작 시 중복 등록 가능.
  2. 미들웨어 0종 — 인증·CORS·rate-limit·timeout 부재.
  3. 부팅 실패 가시성 부족 — `enabled_domains` 가 비면 silent로 빈 detector. structlog/logger 미연결.
- **개선 권고 (impact 순)**
  1. `create_app()` 내부에서 새 `DetectorRegistry` 인스턴스를 만들어 `app.state.registry`에 보관, 라우터는 의존성 주입(`Depends`)으로 접근. 전역 싱글톤 제거.
  2. `from starlette.middleware.trustedhost import TrustedHostMiddleware` 등 미들웨어 정책 도입. Docker 컴포즈 내부망 host만 허용.
  3. `print`/`logger.info`로 등록된 detector 수와 enabled domain을 부팅 라인에 1줄 출력 — observability 1차선.
- **재읽기 권고 레벨**: **낮음**. 사이드 이펙트와 미들웨어 부재만 기억하면 됨.
