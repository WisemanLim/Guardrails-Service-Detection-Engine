# 비교분석 REPORT: Guardrails-Service-Detection-Engine

## 1. 개요 (기준 ref → 적용대상, 2026-06-02)

- 기준(ref, 개선/신규): `DocuGuard-AI-Detection`
- 적용대상(current): `Guardrails-Service-Detection-Engine`
- 관계: ref README에 "Derived from `Guardrails-Service-Detection-Engine` (rsync copy + naming). No behavior change." 명시. ref는 current를 rsync 복사 후 네이밍만 바꾼 형제 프로젝트 + 소량 문서/주석 개선.
- 두 트리의 파일 구조 완전 동일(소스 21개 + 설정). 실행 로직 차이 사실상 없음.
- 결론: ref가 newer지만 "기능 개선"은 없고, 유일한 의미 있는 차이는 `bootstrap.py` docstring 확장 1건. README/pyproject 차이는 전부 네이밍 정체성 차이이며 ref README는 current보다 축약본.

## 2. 구조 비교 (디렉토리/파일 차이)

`.venv`, `.pytest_cache`, `__pycache__`, `.git` 제외 비교.

- 파일 추가·삭제: 없음. 양쪽 소스 트리 1:1 동일.
- current 전용: `.review/CODE-REVIEW-Lv2/...` (리뷰 산출물). 적용 대상 아님.
- ref 전용: `.omc/...` (세션/메모리 메타). 적용 대상 아님.
- 내용 diff 있는 파일은 3개뿐: `bootstrap.py`(주석), `README.md`(네이밍+상세도), `pyproject.toml`(네이밍).

## 3. 의존성 변경 (pyproject.toml diff)

```diff
- name = "guardrails-detection-engine"
+ name = "docuguard-ai-detection"
- description = "PII / sensitive-data detection engine for the MCP Guardrails Service."
+ description = "DocuGuard AI — PII / sensitive-data detection engine (FastAPI)."
```

- 실 의존성 변경 0건. `requirements.txt` diff 없음.
- 차이는 `name`/`description` 텍스트뿐 → 네이밍 차이이므로 미적용(현재 네이밍 보존).

## 4. 개선/추가/수정 항목 (설명 / ref 위치 / 영향도 / QA 리스크)

| # | 분류 | 설명 | ref 위치 | 영향도 | QA 리스크 |
|---|---|---|---|---|---|
| 1 | IMPROVED(문서) | `bootstrap.py` 모듈 docstring 확장. "privacy" leaf 도메인이 별도 detector 없이 always-on `global` baseline 재사용, bootstrap에서 의도적 비-게이팅 이유 명시. P1 detector가 `domain="global"/"*"`라 모든 요청 도메인 포함, Policy 측 245-rule 번들 관계 설명. | `src/detectors/bootstrap.py` docstring | 낮음(주석 only) | 없음 — bytecode 무영향 |
| 2 | NAMING | README 제목/소개 `DocuGuard-AI-Detection` 정체성 | `README.md` L1~ | n/a | 적용 시 정체성 훼손 → 미적용 |
| 3 | NAMING | pyproject `name`/`description` | `pyproject.toml` L6,L8 | n/a | 적용 시 패키지명 변경 → 미적용 |
| 4 | DOC 축약(역행) | ref README는 current보다 상세 내용(detector 13개 표, API JSON 예시, 정규화 규칙, 확장 워크플로우, 성능, M2 로드맵)을 삭제한 축약본 | `README.md` | n/a | 적용 시 정보 손실 → 미적용 |

ADDED 엔드포인트/모델/테스트/버그픽스/탐지로직: 해당 없음(코드 동일).

## 5. 적용 내역 (Applied)

### `src/detectors/bootstrap.py`
- 변경: 모듈 docstring을 ref와 동일하게 확장(항목 #1). 실행 코드(`bootstrap_builtins`, import 분기, P2 silent-skip) 그대로 유지.
- 이유: "privacy" 도메인 비-게이팅 설계 의도(PII = always-on global baseline) 문서화. 비자명 설계 의도를 코드 옆에 보존 → 향후 회귀(privacy 게이팅 추가 시도) 예방. 프로젝트명 미언급이라 현재 정체성과 충돌 없음.

## 6. 미적용/보류 (Deferred)

- `README.md` (#2, #4): 보류. ref는 `DocuGuard-AI-*` 네이밍 + 축약본. current README가 더 풍부하므로 덮으면 정보 손실 + 정체성 훼손. 네이밍-only 분기로 문서화.
- `pyproject.toml` (#3): 보류. `name`/`description`은 패키지 정체성. current=`guardrails-detection-engine` 유지. 의존성 차이 없어 적용 동기 없음.
- `.omc/` (ref 전용): 적용 대상 아님(툴 메타).

네이밍-only 분기: current = `Guardrails-Service-*`/`guardrails-detection-engine`, ref = `DocuGuard-AI-*`/`docuguard-ai-detection`. 동일 코드베이스의 두 브랜딩, 기능 동일.

## 7. 검증 결과 (py_compile/pytest)

환경: 기존 `.venv` 사용(`.venv/bin/python`, Python 3.14). 의존성 추가 없음 → 설치 불필요.

- `python -m py_compile src/detectors/bootstrap.py` → OK
- `python -m pytest tests -q` → 8 passed, 9 warnings, 0.28s

```
........                                                                 [100%]
8 passed, 9 warnings in 0.28s
```

케이스: korean_rrn, us_ssn, email, card_luhn_pass, card_luhn_fail, benign_passes_through, normalize_endpoint_strips_fullwidth, health_lists_detectors — 전부 통과.

경고(비차단, 사전 존재): `Unknown config option: asyncio_mode`, FastAPI `ORJSONResponse is deprecated`. 본 작업 무관.

## 8. QA 체크리스트 & 회귀테스트 권고

- [x] 변경 파일 py_compile 통과
- [x] pytest 8/8 통과
- [x] 적용 변경이 docstring-only(런타임 무영향) 확인
- [x] 현재 네이밍/정체성 보존
- [x] 의존성 변경 없음 → install 회귀 위험 없음
- [ ] (권고) `GUARDRAILS_ENABLED_DOMAINS`에 "privacy"만 줘도 PII detector 미등록 / "global"이면 항상 등록되는지 테스트 추가 → 게이팅 회귀 방지
- [ ] (권고) pytest `asyncio_mode` 경고 출처 정리 또는 `pytest-asyncio` 명시
- [ ] (권고) FastAPI `ORJSONResponse` deprecation 대응 검토(ref/current 공통)
- [ ] (권고) README 네이밍 동기화 책임 주체를 ops 레벨에서 정의(현재 수동 rsync+rename)

회귀 영향: 주석 1건이므로 런타임 회귀 가능성 없음. 동작 동치성은 동일 8-케이스 스위트 통과로 확인.
