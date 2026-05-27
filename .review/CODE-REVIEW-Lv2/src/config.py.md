# `src/config.py` — File Review (Level 2)

## Pre-Review Header

- 역할: 환경변수 → `Settings` frozen dataclass 변환. 모듈 임포트 시점에 `settings` 전역 인스턴스 생성.
- 진입점에서의 거리: 1 (main.py가 직접 import)
- 라인 수: 24
- 주요 export: `Settings`, `settings`, `_csv` (private)
- 의존 모듈 (internal): 없음
- 사용된 외부 패키지: stdlib `os`, `dataclasses`, `typing`
- 부수효과: import 시 `os.getenv` 4회 호출 → `settings` 전역 생성.
- 동시성 모델: 동기. frozen dataclass라 race-free.
- 테스트 커버리지 흔적: 직접 테스트 없음. health 응답을 통해 간접 검증(`tests/test_detectors.py:54`).

---

## Source

```python path=src/config.py lines=1-24
import os
from dataclasses import dataclass, field
from typing import List


def _csv(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    port: int = int(os.getenv("PORT", "8081"))
    log_level: str = os.getenv("LOG_LEVEL", "info")
    enabled_domains: List[str] = field(
        default_factory=lambda: _csv("GUARDRAILS_ENABLED_DOMAINS", "global")
    )
    enabled_locales: List[str] = field(
        default_factory=lambda: _csv("GUARDRAILS_LOCALES", "ko-KR,en")
    )


settings = Settings()
```

**분석 / Analysis (Level 2)**
- L1–3: stdlib만 사용 — 외부 pydantic-settings 의존 회피. 23 LOC로 충분히 read 가능.
- L6–8: `_csv` helper — `,` split + strip + 빈 토큰 제거. **흔한 실수**: 쉼표 뒤 공백 의도치 않게 그대로 두는 코드가 많은데 여기는 strip 처리됨. 단, 따옴표 둘러싼 값(`"a, b",c`)은 단순 split이라 의도와 다르게 깨짐 (현재 ENV 값 형식상 무해).
- L11: `@dataclass(frozen=True)` — 인스턴스 attribute 변경 시 `FrozenInstanceError`. 멀티스레드/멀티워커에서 안전.
- L13: `port: int = int(os.getenv("PORT", "8081"))` — **dataclass 기본값은 클래스 정의 시점에 평가**. 즉 `Settings`가 클래스로 정의되는 import 시점에 `os.getenv("PORT", ...)` 가 실행되어 *클래스 변수*로 박힘. 이후 같은 프로세스에서 `os.environ["PORT"]` 를 바꿔 `Settings()` 를 다시 호출해도 L13의 기본값은 변하지 않음(원래 캡처된 값 사용). 의도가 "런타임 환경 재평가"라면 `default_factory=lambda: int(os.getenv("PORT","8081"))` 가 정확.
- L14: 같은 이슈가 `log_level` 에도 적용.
- L15–20: `enabled_domains` / `enabled_locales` 는 `field(default_factory=lambda: _csv(...))` — factory가 *인스턴스화 시점*에 호출되므로 L13/L14와 동작이 다름. **불일치**: 클래스 내에서 두 가지 평가 시점 (정의 vs 호출)이 혼재. 정합성 측면에서 모두 `default_factory`로 통일 권장.
- L17, L20: `lambda` 클로저 — `_csv` 와 string 리터럴만 캡처해 안전. 가변 객체 캡처 아님.
- L23: `settings = Settings()` — 모듈 전역 싱글톤. 첫 import 시 1회 평가. 이후 `from .config import settings`는 cached module을 가져옴.

**짚어볼 점 / Watch-outs**
- **dataclass 기본값 평가 타이밍 불일치**: `port`/`log_level`은 클래스 정의 시점, `enabled_*`는 인스턴스화 시점. 테스트에서 `monkeypatch.setenv("PORT", "9000"); reload(config)` 안 하면 PORT는 영원히 8081. 의외의 함정.
- `PORT` 가 비숫자 문자열일 때 `int(...)` 가 `ValueError` 던지고 import 자체가 실패 → 컨테이너 부팅 실패. fail-fast 측면에서 OK이나 에러 메시지가 stdlib 기본이라 운영자 친화성 낮음.
- `LOG_LEVEL` 은 캡처만 하고 어디서도 사용 안 됨 — uvicorn은 `--log-level`로 받는 게 일반적이라 dead-ish.
- `_csv` 가 모듈 private 컨벤션(`_` prefix)을 따르지만 `from .config import _csv`가 가능 — 의도적이라면 OK.

---

## File-level Verdict

- **강점**
  1. frozen dataclass + stdlib만으로 24 LOC, 의존성 최소화.
  2. CSV ENV 파싱 헬퍼가 strip + 빈값 필터까지 깔끔.
  3. enabled_* 의 `default_factory` 패턴이 mutable default 안티패턴을 피함.
- **위험**
  1. `port` / `log_level` 기본값 평가 시점 함정 — 테스트·재구성 시 ENV가 안 먹는 미세 버그 유발 가능.
  2. `LOG_LEVEL` 무사용 — 운영자가 변경해도 효과 없음 (관찰자에겐 noise).
  3. 부정확/공백 ENV (`PORT=abc`, `PORT=" "`) 케이스 미보호 — fail-fast이지만 에러 메시지 미가공.
- **개선 권고**
  1. `port`/`log_level`도 `field(default_factory=lambda: ...)` 로 통일.
  2. `log_level` 을 uvicorn 시작 인자로 전달하거나 logger 설정에 실제 사용 — 또는 제거.
  3. ENV 검증 보조 함수 1개 (예: `_int_env(name, default)`) 로 `ValueError` 메시지 친화화.
- **재읽기 권고 레벨**: **낮음**. 24 LOC + 함정 1개만 기억.
