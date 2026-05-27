# `tests/` — Test Suite Abstract

## 역할
FastAPI `TestClient`로 `/detect`, `/normalize`, `/health` 3개 엔드포인트의 회귀 케이스 8건.

## 파일 목록
- [`test_detectors.py`](test_detectors.py.md) — 60 LOC, 8 함수.
- `__init__.py` — 빈 파일 (pytest auto-discover에 필수 아님이지만 패키지화).

## 커버 시나리오
1. `test_korean_rrn_detected` — RRN 13자리.
2. `test_us_ssn_detected` — US SSN.
3. `test_email_detected` — 이메일.
4. `test_card_luhn_pass` — 카드(공백 포함) Luhn 통과.
5. `test_card_luhn_fail` — 카드 Luhn 실패 시 미매치.
6. `test_benign_passes_through` — 무해 한국어 → risk 0.
7. `test_normalize_endpoint_strips_fullwidth` — 전각 → 반각.
8. `test_health_lists_detectors` — `/health`에 `pii.id.rrn.kr` 노출.

## 공백 / Gaps
- `pytest-asyncio` 의존성 선언했지만 비동기 테스트 없음.
- `registry.resolve` 단위 테스트 0 → 도메인/로케일/io_type 분기 회귀 위험.
- `bootstrap_builtins`의 ImportError silent skip 경로 미커버.
- 200KB 길이 입력, ReDoS, 다국어 혼재(`ko-KR` + `ja-JP` 혼합) 케이스 없음.
- `enabled_categories` 화이트리스트 미테스트.
- locale `*` polyfill 경로 미테스트.

## 위험
- 8건 모두 happy-path 위주. failure mode/edge case 부족.
- 모듈 import 시점에 `TestClient(app)` 글로벌로 생성 → 테스트 격리 약함. 향후 `monkeypatch.setenv` 도입 시 import 순서 이슈 가능.
