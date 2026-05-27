# pyproject.toml — 코드 리뷰
> 리뷰 레벨: 2
> [← INDEX.md](.review/CODE-REVIEW-Lv2/INDEX.md)

**파일 요약**
- 역할: 빌드 시스템·메타데이터·의존성 선언, pytest 설정
- 진입점 거리: 0 (이미지 빌드/CI 진입)
- LOC: 37
- export: 패키지 `guardrails-detection-engine` v0.1.0
- 의존 모듈: setuptools≥68, wheel
- 외부 패키지: 런타임 5종, dev 4종(extras), ner 2종(extras)
- 부수효과: `pip install .` 시 src/ 패키지 발견 + 의존성 해결
- 동시성: N/A
- 테스트 커버리지: 본 파일이 `[tool.pytest.ini_options]`로 testpaths/asyncio 모드 정의

```toml path=pyproject.toml lines=1-37
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "guardrails-detection-engine"
version = "0.1.0"
description = "PII / sensitive-data detection engine for the MCP Guardrails Service."
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.27",
  "pydantic>=2.6",
  "regex>=2024.4.16",
  "orjson>=3.9",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.1",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
  "ruff>=0.4",
]
ner = [
  "spacy>=3.7",
  "presidio-analyzer>=2.2",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**분석 / Analysis (Level 2)**

- L1-3 `[build-system]`: PEP 517/518 표준. setuptools 백엔드 + wheel. `setuptools>=68`은 PEP 660 editable, src-layout 안정 버전. **흔한 실수**: poetry/uv 사용 의도였다면 백엔드 미스매치 → 여기서는 setuptools 명시 OK.
- L5-9 `[project]`: PEP 621. `requires-python = ">=3.11"`로 패턴 매칭/`tomllib`/regex 모듈 호환성 확보. `version`이 하드코딩(SemVer) → dynamic versioning 미사용.
- L10-16 `dependencies`: lower bound만 명시 (`>=`). **흔한 실수**: 상한 미지정 → fastapi/pydantic major bump 시 호환성 깨질 수 있음. Pydantic v2 breaking changes 가 잦은 영역 → `pydantic>=2.6,<3` 권장. lock 파일 부재 → 재현성은 Docker 이미지 빌드 시점에 종속.
- L11 `fastapi>=0.110`: starlette/typing 의존 — 0.111 이후 lifespan/router 변경 있어도 `lifespan=` 사용 패턴(main.py)은 안전 범위.
- L12 `uvicorn[standard]`: extras `standard`는 uvloop, httptools, websockets, watchfiles 포함 → 이미지 사이즈 ↑. Docker 워크로드에선 uvloop만 필요할 수 있어 `uvicorn` (no extras) + 명시 의존이 더 슬림.
- L13 `pydantic>=2.6`: v2 API (Field/model_dump). v1 호환 코드 없음. OK.
- L14 `regex>=2024.4.16`: 표준 `re` 대신 `regex` 모듈 — possessive quantifier(`*+`/`++`), Unicode 속성(`\p{...}`), word boundary unicode-aware. ReDoS 완화 도구로도 쓸 수 있음.
- L15 `orjson>=3.9`: `main.py`에서 `ORJSONResponse` 기본 응답 클래스로 사용. 빠른 직렬화, 단 datetime 타임존 표준화/슬롯 클래스 미지원 등 미세 차이 — 본 프로젝트는 dict/str만 직렬화 → 무해.
- L18-23 `[project.optional-dependencies].dev`:
  - `pytest>=8.1`: 8.x는 fixture finalizer 변경. 본 테스트는 fixture 미사용 → 안전.
  - `pytest-asyncio>=0.23`: 0.23부터 `asyncio_mode=auto` 동작 변경(stricter event-loop scoping). 본 테스트는 sync(TestClient) → 미적용.
  - `httpx>=0.27`: TestClient 내부에서 사용 (FastAPI ≥0.110은 starlette TestClient → httpx 기반).
  - `ruff>=0.4`: 의존성 선언만 있고 설정 섹션(`[tool.ruff]`) 미존재 → 사실상 미사용.
- L25-28 `ner` extras: P2/P3 NER 확장 예약. P1 코드에 import 없음 → 설치 안 해도 동작. `presidio-analyzer`는 spaCy + sklearn 트랜지티브 → 이미지 비대화. extras 분리한 것은 적절.
- L30-32 `[tool.setuptools.packages.find]`: src-layout이 아닌 flat-ish (root에 `src/`이지만 `where=["."]`). `include = ["src*"]` → `src`, `src.api`, `src.detectors`, `src.normalize` 모두 패키지로 인식. **흔한 실수 회피**: src-layout일 때 `where=["src"]` + `package_dir={"": "src"}` 가 정석이지만, 이 프로젝트는 `src.main:app` 형태로 import → 현재 설정이 의도와 일치.
- L34-36 pytest 설정: `asyncio_mode = "auto"`로 async def 테스트 자동 마킹. 현재 테스트는 모두 sync이므로 영향 없음. `testpaths = ["tests"]` 명시 → 검색 범위 한정.

**짚어볼 점**

- **버전 상한 부재**: 모든 의존성 `>=`만 사용. 임의 major bump 가능 → 운영 안정성 위험. `pydantic`, `fastapi`는 특히 변경이 잦음.
- **lock 파일 부재**: `uv.lock`, `poetry.lock`, `pip-tools` 산출물 모두 없음. CI에서 `pip install -r requirements.txt`로 매번 해결 → SBOM/취약점 추적 어려움.
- **ruff 의존성 미활용**: 설치만 되고 설정/CI 호출 없음 — dead dependency.
- **`ner` extras 미사용 코드 경로**: `bootstrap.py`는 `manufacturing_food` 모듈 ImportError silent skip 하지만 `presidio`/`spacy` 직접 import는 어디에도 없음. 향후 추가 시 entry point 추적 필요.
- **SBOM/CVE 스캔**: 별도 도구 미설정. 의존성 노출(`fastapi`, `starlette`, `pydantic-core`) 트랜지티브 포함.
- **`tool.setuptools.packages.find`의 `tests` 미포함**: tests 디렉토리가 패키지로 install 되지 않음 — 의도된 동작. dev install에서도 tests는 source-only.
- **`name` vs PyPI 충돌 가능성**: `guardrails-detection-engine` 이름이 PyPI에 등록되지 않은 상태라면 OK. 외부 배포 의도 없으면 무해.

**파일 수준 평가**

- 강점:
  1. PEP 621 표준 메타데이터, build-system 명시.
  2. dev/ner extras 분리 → 런타임 이미지 슬림 유지.
  3. pytest 설정 인라인 통합 → 별도 `pytest.ini` 불필요.

- 위험:
  1. 의존성 상한 미지정으로 향후 major bump 시 breakage.
  2. lock 파일 부재 → 재현성과 보안 추적 한계.
  3. `ruff` 설치만 있고 lint 자동화 없음 — 코드 품질 게이트 부재.

- 개선 권고:
  1. 핵심 의존성에 상한 추가: `pydantic>=2.6,<3`, `fastapi>=0.110,<0.120` 등.
  2. `[tool.ruff]` 섹션 추가 또는 `ruff` extras 제거. CI에서 `ruff check src tests` 게이트화.
  3. `requirements.txt` 대신 `pip-tools` 또는 `uv` lock 도입 → SBOM 안정화. Dockerfile도 lock 기반으로.

- 재읽기 권고 레벨: **1** — 의존성 추가/제거, 버전 정책 변경 시에만 재방문.

---

- 상위 폴더 abstract: [`.review/CODE-REVIEW-Lv2/INDEX.md`](.review/CODE-REVIEW-Lv2/INDEX.md)
- 관련 파일: [`requirements.txt.md`](requirements.txt.md), [`Dockerfile.md`](Dockerfile.md)
