# `src/detectors/base.py` — File Review (Level 2)

## Pre-Review Header

- 역할: Detector ABC. 모든 detector가 따라야 할 6개 속성 + 1개 abstract method.
- 진입점에서의 거리: 2
- 라인 수: 28
- 주요 export: `Detector` (ABC)
- 의존 모듈 (internal): 없음
- 사용된 외부 패키지: stdlib `abc`, `typing`
- 부수효과: 없음 (선언만).
- 동시성 모델: N/A (인터페이스 정의).
- 테스트 커버리지 흔적: 직접 테스트 없음. `RegexDetector` 통해 간접 검증.

---

## Source

```python path=src/detectors/base.py lines=1-28
"""Detector contract. Every detector is plug-in–style so future domains
(P2 manufacturing-food, P3+) only need to register additional concrete classes.

Implementations live under src/detectors/<domain>/...; the registry maps
(domain, locale, io_type) tuples to a list of detectors at boot.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List


class Detector(ABC):
    detector_id: str
    domain: str
    locales: List[str]
    io_types: List[str]
    category: str
    sub_category: str

    @abstractmethod
    def scan(self, text: str) -> Iterable[dict]:
        """Yield match dicts with keys:
        detector_id, category, sub_category, locale, start, end,
        matched_text, confidence, rule_hint (optional).
        """
        ...
```

**분석 / Analysis (Level 2)**
- L1–6: 모듈 docstring — Phase 확장 contract 명시. P2/P3가 새로운 구현 클래스를 추가하는 형태. README와 일관.
- L9: `from abc import ABC, abstractmethod` — Python ABC. 인스턴스화 시 abstract method 누락 시 `TypeError` 발생.
- L13: `class Detector(ABC)` — abstract base. 비-abstract 메서드는 없음.
- L14–19: **6개 클래스 변수 annotation**. Python의 클래스 변수 annotation은 mypy/pyright 시점에서만 강제됨 — 런타임에는 **클래스 속성도 인스턴스 속성도 자동 생성 안 됨**. `RegexDetector.__init__` 가 `self.detector_id = ...` 로 명시 할당해야 함. 만약 새 detector가 `self.locales` 를 빼먹으면 `registry.resolve` 의 `locale not in d.locales` 에서 `AttributeError`.
  - 흔한 실수: ABC에 default 값을 주지 않으면 protocol 처럼 행동하지만 강제력이 없다. `Protocol` 사용 또는 `@dataclass` 기반 ABC가 더 안전.
- L21–27: `@abstractmethod` `scan` — `text: str` → `Iterable[dict]`. dict 키 스키마는 docstring 으로만 명시. 정적 타입 보장 0.
- L23–26: docstring 에 8개 키 + Optional `rule_hint`. `api/detect.py:Match` 와 정확히 일치하지만 형식 강제 없음.
- L27: `...` — Ellipsis 본문. abstract method의 관용 표기 (pass 대신).

**짚어볼 점 / Watch-outs**
- **속성 강제력 0**: 6개 annotation 은 단순 hint. 새 detector가 `category` 를 빼먹어도 인스턴스화는 성공, registry 등록 시점은 통과, `detect.py:54`에서 `m['category']` KeyError 가 첫 매치 발생 시 폭발. fail-late.
- **dict yield 계약**: `TypedDict` 도입 시 mypy strict 환경에서 키 누락 잡힘. 현재는 docstring 신뢰만으로 작동.
- ABC에 `@abstractmethod` 가 `scan` 하나뿐이므로 인스턴스화 시점에 누락 발견. 다만 속성 누락은 인스턴스화 통과 후 첫 호출에서 발견 — debug 비용 차이.
- `Iterable[dict]` — `dict` 만 명시하고 key/value type 미지정. `Iterable[Dict[str, Any]]` 정도가 정직.

---

## File-level Verdict

- **강점**
  1. plugin contract 명시로 확장 의도가 분명.
  2. 28 LOC, 모듈 docstring + 메서드 docstring으로 인터페이스 자기설명.
  3. Phase 확장(P2/P3) 시 base.py 무수정으로 새 detector 추가 가능 (OCP).
- **위험**
  1. 속성 annotation 만으로 런타임 강제력 없음 — 누락 발견이 fail-late.
  2. dict yield 계약이 docstring에만 존재 — 새 detector 회귀 가능.
  3. `scan` 반환 타입이 너무 느슨 (`Iterable[dict]`) — mypy 검출력 약함.
- **개선 권고**
  1. 6개 속성을 `@dataclass(frozen=True)` 베이스 또는 `Protocol` 로 강제.
  2. yield 결과를 `class MatchDict(TypedDict)` 로 정의 후 `Iterable[MatchDict]` 반환.
  3. ruff/mypy CI 라인 도입 — 현재 dev extras에 ruff 있지만 미사용.
- **재읽기 권고 레벨**: **낮음**. contract 잘못 이해 시 risky.
