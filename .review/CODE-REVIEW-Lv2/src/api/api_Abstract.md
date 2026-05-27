# `src/api/` — HTTP Layer Abstract

## 역할
FastAPI `APIRouter` 3개를 모아 외부 노출. 모든 핸들러는 동기(`def`) 함수이며 외부 I/O 없음.

## 파일 목록
- [`detect.py`](detect.py.md) — `POST /detect` 핵심 파이프라인 (63 LOC). 정규화 → registry.resolve → scan iteration → risk 집계.
- [`health.py`](health.py.md) — `GET /health` (17 LOC). 설정·detector id 카탈로그 노출.
- [`normalize.py`](normalize.py.md) — `POST /normalize` (24 LOC). 정규화 + 숫자만 추출 view.
- `__init__.py` — 빈 파일.

## 공통 패턴
- `BaseModel` 요청·응답 정의가 각 모듈에 인라인. 공용 모델 모듈 없음.
- `text: str = Field(..., max_length=200_000)` 패턴 반복 → 입력 길이 DoS 1차선.
- `from ..detectors.registry import registry as detector_registry` 알리아싱 일관.

## 위험
- 핸들러가 동기지만 detector 스캔이 길어지면 이벤트 루프를 점유함 (현재 13개 regex는 O(n) 추정이라 1KB 입력엔 무해).
- 응답에 `matched_text` 원문이 포함되어 PII 누출 위험 — 호출자(MCP Server)가 redact 책임 가정.
- CORS / 인증 / rate limit 없음 — 미들웨어 부재.
