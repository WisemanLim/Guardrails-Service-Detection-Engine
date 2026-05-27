# `src/detectors/` — Detection Core Abstract

## 역할
Detector 계약(ABC), 등록소(registry), 부팅 와이어링(bootstrap), 실제 룰 정의(global_privacy), 체크섬(luhn)으로 구성된 핵심 도메인 계층.

## 파일 목록
- [`base.py`](base.py.md) — `Detector` ABC. `scan(text) -> Iterable[dict]` 계약 + 6개 클래스 속성 (28 LOC).
- [`registry.py`](registry.py.md) — `DetectorRegistry.register/list_ids/resolve` + 모듈 끝 싱글톤 (47 LOC).
- [`bootstrap.py`](bootstrap.py.md) — `bootstrap_builtins(reg, enabled_domains)` 도메인 키로 register_*() 호출 (25 LOC).
- [`global_privacy.py`](global_privacy.py.md) — `RegexDetector` 클래스 + 13개 P1 PII detector 등록 (214 LOC).
- [`luhn.py`](luhn.py.md) — 카드 체크섬 한 함수 (14 LOC).
- `__init__.py` — 빈 파일.

## 공통 패턴
- detector는 dict yielder. 키 schema는 `base.py` docstring에만 명시 → 암묵 계약.
- 모든 패턴 검색은 `regex` 모듈(`re`로 alias) 사용. `IGNORECASE` 기본.
- ABC가 abstract method 없는 속성을 인스턴스에 직접 할당(`self.detector_id = ...`) → mypy strict 모드에서는 클래스 속성 vs 인스턴스 속성 혼동.

## 위험
- `registry.resolve`의 `{"*", domain, "global"}` 집합 비교가 의도와 다르게 동작할 수 있음 — global detector가 모든 요청 도메인을 통과 (P2 격리 약화).
- `RegexDetector` 의 `pattern=r"\b(?:\d[ -]*?){13,19}\b"` 는 ReDoS 잠재.
- detector dict 키 누락 시 `Match(**m)` 가 `ValidationError` 던져 500 응답.

## 확장 계약
- P2 도입 시 `manufacturing_food.py` 모듈만 추가하면 `bootstrap.py` 가 `ImportError` 캐치 후 silent skip — P1 단독 배포는 무변경.
