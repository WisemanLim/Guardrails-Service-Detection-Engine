# `src/detectors/registry.py` — File Review (Level 2)

## Pre-Review Header

- 역할: detector 등록·열거·필터(`resolve`) + 모듈 끝 싱글톤.
- 진입점에서의 거리: 1 (main, api/health, api/detect 가 import)
- 라인 수: 47
- 주요 export: `DetectorRegistry`, `registry` (singleton)
- 의존 모듈 (internal): `.base.Detector`
- 사용된 외부 패키지: stdlib `typing`
- 부수효과: 모듈 import 시 빈 `DetectorRegistry()` 1개 생성.
- 동시성 모델: 등록은 부팅 시점 단일 스레드. resolve는 read-only generator → race-free.
- 테스트 커버리지 흔적: 직접 단위 테스트 없음. detect endpoint 통해 간접.

---

## Source

```python path=src/detectors/registry.py lines=1-47
"""Detector registry. Domain-scoped, swappable, hot-extensible.

Phase rollout contract:
  P1 enables {"global"}.
  P2 will additionally register detectors for "manufacturing-food" without
  touching P1 behavior. The registry filters by enabled_domains at boot
  (via bootstrap_builtins) and per-request via resolve(domain=...).
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from .base import Detector


class DetectorRegistry:
    def __init__(self) -> None:
        self._detectors: List[Detector] = []

    def register(self, detector: Detector) -> None:
        self._detectors.append(detector)

    def list_ids(self) -> List[str]:
        return [d.detector_id for d in self._detectors]

    def resolve(
        self,
        *,
        domain: str,
        locale: str,
        io_type: str,
        categories: Optional[List[str]] = None,
    ) -> Iterable[Detector]:
        for d in self._detectors:
            if d.domain not in {"*", domain, "global"}:
                continue
            if locale not in d.locales and "*" not in d.locales:
                continue
            if io_type not in d.io_types and "both" not in d.io_types:
                continue
            if categories and d.category not in categories:
                continue
            yield d


registry = DetectorRegistry()
```

**분석 / Analysis (Level 2)**
- L1–8: docstring — Phase rollout contract. "boot via bootstrap_builtins" + "per-request via resolve" 2단계 필터링 의도.
- L11: `Iterable, List, Optional` — Python 3.11에선 `list[str]` 가능하지만 typing module 사용. 일관성 OK.
- L16–18: `_detectors: List[Detector]` — 단순 list. 등록 순서가 곧 resolve 순서 → detect 매치 순서.
- L20–21: `register` — append. dedup 검사 없음. 같은 detector_id를 두 번 등록 시 매치도 2배 (테스트 환경에서 `create_app()` 두 번 호출 가능성, see main.py 리뷰).
- L23–24: `list_ids` — 매번 new list comprehension. health endpoint가 호출.
- L26–43: `resolve` 핵심
  - L28 `*` — 키워드-only 강제. 안전한 호출 컨벤션.
  - L34: `for d in self._detectors` — 순회.
  - **L35: `if d.domain not in {"*", domain, "global"}: continue`** — set membership. domain==`manufacturing-food` 요청 시:
    - `d.domain == "*"`: 통과 (예상)
    - `d.domain == "manufacturing-food"`: 통과 (예상)
    - **`d.domain == "global"`: 통과 (예기치 못한 leak)** — global detector가 모든 도메인 요청에 항상 적용됨.
    - 의도가 "global은 baseline이므로 모든 도메인에 적용"이라면 OK. 그러나 P2 격리(예: manufacturing-food 전용 모드)를 원하면 이 줄이 leak 통로.
    - 반대로 domain==`global` 요청에 `d.domain == "manufacturing-food"` 인 detector는 차단 — 정상.
  - L37: `if locale not in d.locales and "*" not in d.locales` — locale 와일드카드 지원. detector가 `locales=["*"]` 면 모든 locale 통과. 합리적.
  - L39: io_type 동일 패턴. `"both"` 가 detector 측 wildcard.
  - L41: `if categories and d.category not in categories` — `enabled_categories` 화이트리스트. `None` 또는 `[]` 면 적용 안 함. **흔한 실수**: 빈 리스트 의미가 "전부 차단" 인지 "필터 없음" 인지 모호. 여기선 falsy 처리 → "필터 없음". 호출자가 빈 리스트로 "0건 의도" 했다면 의도와 다름.
  - L43: `yield d` — generator. 호출자(`detect.py:51`) 즉시 소비.
- L46: `registry = DetectorRegistry()` — 모듈 전역 singleton. 모든 import 가 동일 인스턴스 공유.

**짚어볼 점 / Watch-outs**
- **L35 의도 명확화 필요**: global detector가 모든 요청 도메인에 always-on. README 의 "global = baseline" 의도와 일치하지만 코드에 주석으로 명시 권장. 의도 아니면 명백한 버그.
- **register dedup 부재**: `create_app()` 재호출 시 detector 누적. health에서 detector_id 중복으로 노출됨.
- **L41 빈 리스트 ambiguity**: `categories=[]` 의미를 코드 또는 docstring으로 명확화.
- **순서 의존성**: 매치 결과가 detector 등록 순서를 따른다. 카드 detector 가 RRN detector 보다 뒤에 등록되면 같은 13자리 숫자가 RRN으로 먼저 잡힘. 현 `global_privacy.py` 에선 RRN이 먼저 → 의도와 일치.
- **`Iterable` vs `Iterator`**: `resolve` 는 generator라 1회 소비. 호출자가 두 번 순회 시 두 번째는 빈 결과. 현 코드는 1회 소비라 안전.

---

## File-level Verdict

- **강점**
  1. 47 LOC, plug-in registry 의도 깔끔.
  2. wildcard (`*`/`both`) 두 축 일관 처리.
  3. generator 기반 lazy filter — 부담 낮음.
- **위험**
  1. `{"*", domain, "global"}` 집합 의도 모호 — global이 모든 도메인 통과.
  2. dedup 부재 → 재부팅/재팩토리 시 중복 등록 폭발 가능.
  3. `categories=[]` 의미 정의 부재.
- **개선 권고**
  1. L35에 `# global = always-on baseline (intentional)` 주석 추가, 또는 의도가 다르면 `{"*", domain}` 으로 수정.
  2. `register`에서 `detector_id` 중복 검사 후 `ValueError` 또는 warning.
  3. `resolve`의 4개 필터 각각에 대해 단위 테스트 (8~16 케이스) 추가.
- **재읽기 권고 레벨**: **중**. 도메인 분리 정책의 핵심 분기. P2 도입 직전엔 반드시 재검토.
