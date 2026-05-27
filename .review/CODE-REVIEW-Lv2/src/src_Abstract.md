# `src/` — 패키지 루트 Abstract

## 역할
FastAPI app factory(`main.py`)와 환경설정 캡처(`config.py`) 두 모듈로 구성된 진입 패키지. `src/__init__.py`는 빈 파일로 패키지 표시만 담당.

## 파일 목록
- [`main.py`](main.py.md) — FastAPI 인스턴스 생성, detector 부트스트랩, router 마운트 (23 LOC).
- [`config.py`](config.py.md) — ENV → frozen dataclass `Settings`, 모듈 import 시점에 `settings` 싱글톤 생성 (24 LOC).
- `__init__.py` — 빈 파일. 패키지 식별용.

## 공통 패턴
- 모듈 import 부수효과로 전역 싱글톤(`app`, `settings`) 노출.
- 외부 I/O 없음, 순수 in-memory 부팅.

## 호출 관계
`uvicorn src.main:app` → `main.py` import → `config.py` import → `detectors.registry` import → `detectors.bootstrap` 호출 → 13개 detector 등록 → router 마운트.

## 위험
- `settings`가 import-time에 캡처되므로 테스트에서 `monkeypatch.setenv` 후 재import 필요(현재 테스트는 ENV 변경 없이 default 사용 → 무해).
