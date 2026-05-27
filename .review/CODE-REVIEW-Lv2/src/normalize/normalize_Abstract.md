# `src/normalize/` — Input Normalization Abstract

## 역할
입력 텍스트의 NFKC 정규화 + 다중 공백 단일화. 모든 detector가 호출 전에 거쳐가는 공용 전처리.

## 파일 목록
- [`normalizer.py`](normalizer.py.md) — `normalize_text(text)` 함수 (32 LOC).
- `__init__.py` — 빈 파일.

## 핵심 동작
1. 빈 문자열 short-circuit.
2. `unicodedata.normalize("NFKC", text)` — 전각/반각 통일.
3. 공백 collapse (newline은 보존하여 위치 정보 유지).
4. `.strip()` 으로 양끝 공백 제거.

## 위험
- 4단계 `.strip()`이 detector 결과의 start/end 인덱스가 가리키는 좌표계를 '정규화 후 문자열' 기준으로만 의미를 갖게 만듦. 즉 클라이언트는 정규화 후 텍스트를 반드시 보관해야 redaction 가능 — `/detect` 응답에 `normalized_text`가 함께 반환되는 이유.
- NFKC가 일부 한자 변형을 변경 → 의미 변화 가능 (PII 탐지엔 영향 적지만, 일본어 한자 변환에 주의).
- combining mark "edge strip" 주석은 있으나 코드엔 미구현 — docstring과 실제 동작 불일치.
