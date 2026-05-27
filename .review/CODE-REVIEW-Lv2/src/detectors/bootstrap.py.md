# `src/detectors/bootstrap.py` — File Review (Level 2)

## Pre-Review Header

- 역할: 활성 도메인 키별로 `register_<phase>()` 호출. P2 모듈 부재 시 silent skip.
- 진입점에서의 거리: 1 (main.py가 호출)
- 라인 수: 25
- 주요 export: `bootstrap_builtins(reg, *, enabled_domains)`
- 의존 모듈 (internal): `.registry.DetectorRegistry`, `.global_privacy.register_global_privacy`, (Optional) `.manufacturing_food.register_manufacturing_food`
- 사용된 외부 패키지: stdlib `typing`
- 부수효과: registry 에 detector append.
- 동시성 모델: 부팅 시점 단일 스레드.
- 테스트 커버리지 흔적: 직접 단위 테스트 없음. import 자체가 main.py 통해 테스트에서 트리거.

---

## Source

```python path=src/detectors/bootstrap.py lines=1-25
"""Boot-time detector wiring. Each phase adds a register_<phase>() call.

P1: register_global_privacy()    — domain-agnostic PII baseline.
P2: register_manufacturing_food() — placeholder, not yet implemented.
"""
from __future__ import annotations

from typing import Iterable

from .registry import DetectorRegistry


def bootstrap_builtins(reg: DetectorRegistry, *, enabled_domains: Iterable[str]) -> None:
    domains = set(enabled_domains)
    if "global" in domains:
        from .global_privacy import register_global_privacy
        register_global_privacy(reg)
    if "manufacturing-food" in domains:
        try:
            from .manufacturing_food import register_manufacturing_food  # type: ignore
        except ImportError:
            # P2 bundle not yet shipped — silently skip.
            return
        register_manufacturing_food(reg)
```

**분석 / Analysis (Level 2)**
- L1–5: docstring — phase 매핑 명시. P2 가 placeholder.
- L8: `Iterable[str]` 인자 — list/set/generator 모두 허용.
- L13: `def bootstrap_builtins(reg, *, enabled_domains)` — registry 주입 + 키워드-only 옵션. main.py 가 `settings.enabled_domains` (list) 전달.
- L14: `domains = set(enabled_domains)` — generator 소진 + set 변환 (O(1) membership check). idempotent.
- L15–17: `"global"` 분기. **함수 내 지연 import** — module-level 부트시점에 global_privacy.py 의 13개 regex compile 비용을 분기 안쪽으로 미룸. 비활성 도메인은 import 안 됨 → cold start 빠름.
- L18–24: `"manufacturing-food"` 분기.
  - L19–22 try/except ImportError — P2 모듈 부재 시 silent skip. README와 일치.
  - **L23 `return`** — 여기 주의. P2 ImportError 시 함수 즉시 종료. 만약 향후 P3 분기 (`"finance"` 등) 가 추가되면 P2 ImportError가 P3 등록까지 막아버림. 의도라면 OK이나 미래 확장 시 회귀 위험. `return` 대신 `pass` 가 안전.
  - L24: ImportError 안 났을 때만 `register_manufacturing_food(reg)` 실행. import 후 호출 분리 — 부분 import 성공 후 register 호출 실패는 별도 catch 없음.
- 코드 외부 영향: silent skip 정책은 운영 가시성에 trade-off. 운영자가 `GUARDRAILS_ENABLED_DOMAINS=manufacturing-food` 로 설정했는데 모듈 부재 시 detector 0건, health=ok, 알 길 없음.

**짚어볼 점 / Watch-outs**
- **L23 `return` → P3 등록 차단 회귀 위험**. 향후 분기 추가 시 첫 번째로 발견할 함정.
- **silent skip 가시성 0**: `logger.warning("P2 bundle not loaded")` 한 줄 정도가 운영자에게 큰 도움. 현재 logger 미연결.
- **부분 register 실패 미처리**: `register_global_privacy(reg)` 내부에서 예외 나면 함수 자체가 throw → app 부팅 실패. fail-fast 측면에선 OK이나 partial wired 상태는 회피 가능.
- **enabled_domains에 알 수 없는 도메인 (`"finance"` 등) 포함 시**: 분기 미매칭 → silent ignore. 오타 진단 불가.
- `# type: ignore` (L20) — manufacturing_food 모듈 부재를 mypy에 알리는 표시. 명시적이라 OK.

---

## File-level Verdict

- **강점**
  1. 25 LOC, plug-in 도메인 와이어링이 한눈에 들어옴.
  2. 지연 import로 cold start 최소화 + 의존성 격리.
  3. P2 ImportError silent skip으로 P1 단독 배포 안전 보장.
- **위험**
  1. L23 `return` 이 향후 분기 추가 시 silent 회귀 유발.
  2. silent skip 가시성 0 — 운영 진단 어려움.
  3. unknown domain (오타 등) silent ignore.
- **개선 권고**
  1. L23 `return` → `pass` 로 변경 (또는 try 내부에 한정).
  2. `logger.info`/`warning` 으로 phase별 등록 결과 1줄 출력.
  3. 알 수 없는 도메인은 warn 또는 startup fail-fast — settings layer 에서 validation.
- **재읽기 권고 레벨**: **낮음** (25 LOC) — 단, P2 도입 직전 반드시 재읽기.
